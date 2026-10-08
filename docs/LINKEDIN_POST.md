# LinkedIn post draft

I just built a serverless AI document analyzer on AWS, and here is what I learned.

Upload a PDF or image to S3 and, within seconds, a pipeline:
-> extracts the text with Amazon Textract
-> analyzes sentiment and named entities with Amazon Comprehend
-> stores the structured result in DynamoDB

Stack: S3, Lambda (Python 3.12), Textract, Comprehend, DynamoDB, IAM, CloudWatch.

What made it more than a tutorial for me:
- Least-privilege IAM instead of FullAccess managed policies
- Fixed a real bug: S3 event keys are URL-encoded, so files with spaces failed
- Comprehend's input limit is in bytes, not characters
- Graceful fallback to a rule-based analyzer if Comprehend is unavailable
- Tore everything down afterwards to keep costs at zero

My background is IT audit and cybersecurity GRC, so I'm especially interested in how services like this handle access control, logging and data protection. I'm now moving into cloud and software roles.

Code and architecture write-up: [PASTE GITHUB LINK]

Feedback is welcome, and I'm open to remote cloud opportunities.

#AWS #Serverless #CloudComputing #Python #Textract #DevOps #OpenToWork
