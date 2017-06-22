#!/bin/bash

python scripts/main.py  # Download Salesforce data, transform and save to CSV.
bash scripts/upload.sh  # Upload to S3
