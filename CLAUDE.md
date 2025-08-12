# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python application that automatically transcribes Apple Voice Memos and integrates them into an Obsidian vault. It processes audio files from the Apple Voice Memos directory, transcribes them using OpenAI's Whisper API, generates summaries, and creates organized notes in Obsidian.

## Architecture

### Core Components

1. **Config Class** (`main.py:12-47`)
   - Manages all environment variables and paths
   - Validates configuration on initialization
   - Provides computed properties for various Obsidian folders

2. **MemoProcessor Class** (`main.py:50-283`)
   - Main processing engine
   - Handles file discovery, transcription, and Obsidian integration
   - Detects duplicates by MD5 hashing existing files in attachments folder
   - Key methods:
     - `get_unprocessed_memos()`: Filters memos by date and processing status
     - `transcribe_audio()`: Uses OpenAI Whisper API
     - `generate_summary_and_title()`: Uses GPT-4o-mini for summarization
     - `create_obsidian_note()`: Generates markdown notes
     - `update_daily_note()`: Links memos to daily diary entries

### Data Flow

1. Scan Apple Voice Memos directory (`/Users/guistiebler/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings`)
2. Scan Obsidian attachments folder and hash existing audio files
3. Filter by creation date (if `PROCESS_FILES_AFTER_DATE` is set)
4. Check memo hashes against existing file hashes to detect duplicates
5. Transcribe unprocessed audio using OpenAI Whisper
6. Generate title and summary using GPT-4o-mini
7. Copy audio file to Obsidian attachments with descriptive name
8. Create markdown note with transcription
9. Update or create daily diary note with reference

## Development Commands

```bash
# Install dependencies
pip install -e .
# or
pip install openai

# Run the application
python main.py

# Set up environment (using mise)
mise install
```

## Environment Configuration

The project uses `mise.toml` to load environment variables from `.env`. Required variables:

- `OPENAI_API_KEY`: OpenAI API key for transcription and summarization
- `OBSIDIAN_VAULT_PATH`: Absolute path to Obsidian vault
- `OBSIDIAN_ATTACHMENTS_FOLDER`: Relative path for audio files (default: "attachments")
- `OBSIDIAN_DIARY_FOLDER`: Relative path for daily notes (default: "diary")
- `OBSIDIAN_NOTES_FOLDER`: Relative path for memo notes (default: "notes/memos")
- `PROCESS_FILES_AFTER_DATE`: Optional date filter in YYYY-MM-DD format

## File Structure in Obsidian

The application creates:
- Audio files: `{vault}/attachments/{timestamp}_{summary}.m4a`
- Memo notes: `{vault}/notes/memos/{timestamp}_{title}.md`
- Daily notes: `{vault}/diary/{YYYY-MM-DD}.md`

## Duplicate Detection

The application scans the attachments folder and computes MD5 hashes of existing audio files to prevent reprocessing. This ensures memos are not duplicated even if they're renamed or moved.

## Error Handling

- Configuration validation on startup
- Graceful API failure handling with error messages
- Skips files with empty transcriptions
- Full stack traces for debugging unexpected errors