# PHOENIX

A unified, privacy-first, open-source ecosystem of tools designed to democratize access to high-quality media consumption, network security, and digital self-defense.

## Vision Statement
A unified, privacy-first, open-source ecosystem of tools designed to democratize access to high-quality media consumption, network security, and digital self-defense.

## Core Principles
1. Privacy by design
2. Minimal resource footprint
3. Modular architecture
4. Beautiful, terminal-native interface
5. No corporate dependencies
6. Educational value embedded in every component

## Design Philosophy

The modern internet is a surveillance engine. Every click, every scroll, every pause—monetized, analyzed, sold. We are not users. We are products.

Phoenix is an act of resistance.

It is a suite of tools that reclaims agency. That treats the user as a human being, not a data point. That prioritizes function over flash, substance over style, and privacy over profit.

Every component must be:
- Fast (sub-100ms response times)
- Elegant (clean code, minimal dependencies)
- Accessible (works offline, works on low-end hardware)
- Educational (users should understand how it works)
- Beautiful (terminal aesthetics, retro-futurist design)

## Modules

### 1. SONGBIRD
A terminal-based music player and library manager.

Features:
- Lossless audio playback (requires pydub and ffmpeg)
- Music library management with metadata extraction (via mutagen)
- Playlist creation and management
- Mood-based playlist generation
- Vinyl linking (connect digital tracks to physical vinyl records)
- Library statistics
- No telemetry. No tracking. No ads.

### 2. PROJECTOR
A film and TV tracking system with recommendation engine.

Features:
- Personal watchlist management
- Mark as watched with personal ratings
- Metadata extraction from media files (basic support for video formats)
- Mood-based recommendations
- Watchlist management
- Library statistics
- Simulated Letterboxd integration (read-only placeholder)
- No telemetry. No tracking. No ads.

### 3. CIPHER
A network privacy and security toolkit.

Features:
- Encrypted password vault (using cryptography library)
- WireGuard VPN configuration generator
- DNS leak tester (educational)
- Firewall rule generator
- Network traffic visualizer (educational mode, requires scapy and privileges)
- All data stored locally and encrypted where appropriate
- No telemetry. No tracking. No ads.

### 4. VINYL
A physical media cataloging system.

Features:
- Vinyl record cataloging by barcode, Discogs ID, or manual entry
- Barcode scanning framework (simulated, with Discogs API lookup)
- Condition tracking
- Playback statistics (play count, last played)
- Now Spinning display (shows most recently played record)
- Read-only Discogs API integration (search by query)
- Link to digital tracks (if using SONGBIRD)
- No telemetry. No tracking. No ads.

### 5. WHISPERNET
The unified interface. The hub.

Features:
- Plugin architecture for all modules
- Unified CLI with subcommands for each module
- No telemetry. No tracking. No ads.

## Project Structure

```
phoenix/
├── src/
│   ├── songbird/       # Music player and library manager
│   ├── projector/      # Film/TV tracking system
│   ├── cipher/         # Network privacy and security toolkit
│   ├── vinyl/          # Physical media cataloging
│   └── whispernet/     # Unified CLI and hub
├── tests/              # Test suites for each module
├── docs/               # Documentation
├── configs/            # Configuration files
├── scripts/            # Utility scripts
├── assets/             # Icons, themes, etc.
├── README.md
├── LICENSE
└── pyproject.toml
```

## Getting Started

### Prerequisites
- Python 3.8+
- Git
- Depending on modules: FFmpeg (for audio/video), libssl, etc.

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd phoenix

# Install dependencies
# For full functionality, install with all extras:
pip install -e .[full]

# Or install specific modules:
# pip install -e .[songbird]
# pip install -e .[projector]
# pip install -e .[cipher]
# pip install -e .[vinyl]

# Run the unified CLI
whispernet --help
```

## Development

### Coding Standards
- Follow PEP 8 for Python code
- Write clear, concise comments
- Keep functions small and focused
- Prioritize readability over cleverness
- Add type hints where possible

### Testing
- Write unit tests for all functions
- Integration tests for module interactions
- End-to-end tests for CLI workflows
- Run tests with: `pytest`

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing
Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## Acknowledgments
Inspired by the need for privacy-respecting, user-centric software in an age of surveillance capitalism.