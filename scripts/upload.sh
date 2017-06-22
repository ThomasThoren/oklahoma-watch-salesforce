#!/bin/bash

aws s3 sync \
  data/ \
  s3://membership.oklahomawatch.org/ \
  --acl public-read \
  --cache-control "private" \
  --expires "2012-12-21 00:00:00 -0000" \
  --exclude ".DS_Store"
