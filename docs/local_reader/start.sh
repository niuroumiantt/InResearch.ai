#!/bin/sh
# Architecture v2 supersedes the destructive one-shot batch launcher.
# This compatibility entry only inspects the already installed Spark service.
set -eu
exec ssh spark systemctl --user status inresearch-reader.service --no-pager
