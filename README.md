# Polytoria Archive

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![GitHub Repo stars](https://img.shields.io/github/stars/lxvdev/polytoria-archive?style=for-the-badge)](https://github.com/lxvdev/polytoria-archive/stargazers)
[![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/lxvdev/polytoria-archive/total?style=for-the-badge)](https://github.com/lxvdev/polytoria-archive/releases)

This repository periodically fetches the Polytoria API and downloads new versions of the client and creator when updates are available, then publishes them as GitHub releases.

[Go to releases](https://github.com/lxvdev/polytoria-archive/releases)

## Purpose

The purpose of this repository is to preserve the history of Polytoria by archiving all versions of the client and creator, starting from version 1.5.6. As Polytoria evolves, older versions may become unavailable from official sources, making this archive essential for preserving the game's development timeline.

## How it works

The repository contains a Python script (`archiver.py`) that:

1. Checks the Polytoria API for the latest versions
2. Compares them against previously archived versions stored in `versions.json`
3. Downloads any new versions found
4. Creates GitHub releases for each new archived version
5. Updates the version tracking file

## What's Archived

- **Creator** - The game creation tool
- **Client** - The game client

## Files

- `archiver.py` - The main archiving script
- `versions.json` - Tracks the latest archived versions

## Automation

This repository is designed to be run periodically via GitHub Actions to automatically archive new releases as they're published by Polytoria.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Andrew (@lxvdev)
