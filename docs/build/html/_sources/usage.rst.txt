.. _usage:

Usage
=====

Heroku hosts the application and runs the ``Procfile`` once per day. This includes ``scripts/main.py`` to download and process Salesforce donor data and ``scripts/upload.sh`` to upload CSV files to an AWS S3 bucket.

The TablePress plugin for WordPress then downloads those CSV files from S3 once per day.
