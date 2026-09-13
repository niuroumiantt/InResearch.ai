#!/usr/bin/env bash
# Install only this reader. Publication has its own separately managed units.
set -euo pipefail
umask 077
reader_repo="$HOME/code/inresearch.ai"
reader_config="$HOME/.config/inresearch.ai"
reader_units="$HOME/.config/systemd/user"
if [[ ! -f "$reader_repo/manage.py" ]]; then
  echo 'Expected canonical checkout: ~/code/inresearch.ai' >&2
  exit 1
fi
if [[ "$(uname -s)" != Linux ]]; then
  echo 'This installer requires Linux user systemd.' >&2
  exit 1
fi
mkdir -p "$reader_config" "$reader_units"
if [[ ! -e "$reader_config/reader.env" ]]; then
  install -m 600 "$reader_repo/deploy/spark-reader/reader.env.example" "$reader_config/reader.env"
fi
python3 "$reader_repo/manage.py" reader init
install -m 600 "$reader_repo/deploy/spark-reader/inresearch-reader.service" "$reader_units/inresearch-reader.service"
systemctl --user daemon-reload
systemctl --user enable inresearch-reader.service
if [[ "${1:-}" == --start ]]; then
  systemctl --user restart inresearch-reader.service
fi
printf '%s\n' 'Installed user service. Raw materials, permanent catalog and originals were preserved.'
