#!/usr/bin/env bash
set -e
cd ~/Documents/PYTHON/iblscripts/deploy/serverpc/training
source ~/Documents/PYTHON/envs/iblenv/bin/activate
python training.py extract /mnt/s0/Data/Subjects/ --dry=False
