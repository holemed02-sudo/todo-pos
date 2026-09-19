# ToDo POS

Windows desktop POS for the ToDo shop.

## Current baseline

This repository now contains the full source of the previously shared **ToDo POS 1.0.2** baseline as a source snapshot under `baseline/`. The runtime SQLite database and product images are intentionally not included.

## What happens next

The open GitHub issues are the active engineering backlog. The baseline is only the starting point; fixes are tracked separately.

## Windows build

GitHub Actions contains a Windows build workflow that unpacks the baseline source, runs the core tests, and builds a portable `ToDo` folder with PyInstaller.
