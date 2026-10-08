"""Smart Doc Analyzer - S3 upload -> Textract -> Comprehend -> DynamoDB."""
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("TABLE_NAME", "cloudwithshad-documents")
# "comprehend" (ML, small cost) or "python" (free, rule-based fallback)
ANALYSIS_MODE = os.environ.get("ANALYSIS_MODE", "comprehend").lower()

textract = boto3.client("textract")
comprehend = boto3.client("comprehend")
table = boto3.resource("dynamodb").Table(TABLE_NAME)

POSITIVE = {"good", "great", "excellent", "positive", "happy", "best", "strong",
            "success", "improve", "benefit", "effective", "reliable", "achieve"}
NEGATIVE = {"bad", "poor", "terrible", "negative", "worst", "fail", "failure",
            "weak", "problem", "issue", "delay", "risk", "loss", "concern", "error"}


def truncate_bytes(text: str, limit: int = 4900) -> str:
    """Comprehend's limit is in UTF-8 bytes, not characters."""
    return text.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def python_analysis(text: str):
    words = re.findall(r"[a-z']+", text.lower())
    pos = sum(w in POSITIVE for w in words)
    neg = sum(w in NEGATIVE for w in words)
    label = "POSITIVE" if pos > neg else "NEGATIVE" if neg > pos else "NEUTRAL"
    scores = {"Positive": str(pos), "Negative": str(neg)}
    names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text)
    entities = [{"text": n, "type": "PROPER_NOUN", "score": "0.80"}
                for n in dict.fromkeys(names)][:10]
    return label, scores, entities


def comprehend_analysis(text: str):
    snippet = truncate_bytes(text)
    sent = comprehend.detect_sentiment(Text=snippet, LanguageCode="en")
    ents = comprehend.detect_entities(Text=snippet, LanguageCode="en")
    entities = [{"text": e["Text"], "type": e["Type"], "score": str(round(e["Score"], 4))}
                for e in sorted(ents["Entities"], key=lambda e: -e["Score"])[:10]]
    scores = {k: str(round(v, 4)) for k, v in sent["SentimentScore"].items()}
    return sent["Sentiment"], scores, entities


def lambda_handler(event, context):
    record = event["Records"][0]["s3"]
    bucket = record["bucket"]["name"]
    key = unquote_plus(record["object"]["key"])  # S3 events URL-encode keys

    if not key.startswith("uploads/") or key.endswith("/"):
        return {"status": "skipped", "key": key}

    logger.info("Processing s3://%s/%s", bucket, key)
    try:
        resp = textract.detect_document_text(
            Document={"S3Object": {"Bucket": bucket, "Name": key}})
    except ClientError:
        logger.exception("Textract failed for %s", key)
        raise

    text = " ".join(b["Text"] for b in resp["Blocks"] if b["BlockType"] == "LINE")
    if not text.strip():
        logger.warning("No text detected in %s", key)
        return {"status": "no_text", "key": key}

    mode = ANALYSIS_MODE
    try:
        if mode == "comprehend":
            sentiment, scores, entities = comprehend_analysis(text)
        else:
            sentiment, scores, entities = python_analysis(text)
    except ClientError:
        logger.exception("Comprehend unavailable, falling back to python")
        mode = "python"
        sentiment, scores, entities = python_analysis(text)

    doc_id = str(uuid.uuid4())
    table.put_item(Item={
        "document_id": doc_id,
        "filename": key,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "extracted_text": text[:1000],
        "sentiment": sentiment,
        "sentiment_scores": scores,
        "entities": entities,
        "analysis_method": mode,
    })
    logger.info("Saved %s (%s, %d entities)", doc_id, sentiment, len(entities))
    return {"statusCode": 200, "document_id": doc_id,
            "sentiment": sentiment, "entity_count": len(entities)}
