# Memo Transcription to Obsidian

Automatically transcribe Apple Voice Memos and organize them in your Obsidian vault with AI-generated summaries and daily note integration.

## Features

- **Automatic Transcription** - Transcribes Apple Voice Memos using OpenAI's Whisper API
- **Smart Summaries** - Generates titles and summaries using GPT-4o-mini
- **Obsidian Integration** - Creates organized markdown notes in your vault
- **Daily Notes** - Automatically links memos to daily diary entries
- **Duplicate Detection** - Tracks processed files to avoid reprocessing
- **Date Filtering** - Process only memos created after a specific date
- **Smart Naming** - Renames audio files with descriptive AI-generated names

## Prerequisites

- Python 3.13+
- macOS (for Apple Voice Memos access)
- OpenAI API key
- Obsidian vault

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/memo-transcription-to-obsidian.git
cd memo-transcription-to-obsidian
```

2. Install dependencies:
```bash
pip install -e .
# or
pip install openai
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Configuration

Create a `.env` file with the following variables:

```env
OPENAI_API_KEY=your-openai-api-key
OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
OBSIDIAN_ATTACHMENTS_FOLDER=attachments
OBSIDIAN_DIARY_FOLDER=diary
OBSIDIAN_NOTES_FOLDER=notes/memos
PROCESS_FILES_AFTER_DATE=2024-01-01
OPENAI_WHISPER_MODEL=whisper-1
OPENAI_CHAT_MODEL=gpt-4o-mini
```

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key for transcription and summarization | - |
| `OBSIDIAN_VAULT_PATH` | Yes | Absolute path to your Obsidian vault | - |
| `OBSIDIAN_ATTACHMENTS_FOLDER` | No | Folder for audio files (relative to vault) | `attachments` |
| `OBSIDIAN_DIARY_FOLDER` | No | Folder for daily notes (relative to vault) | `diary` |
| `OBSIDIAN_NOTES_FOLDER` | No | Folder for memo notes (relative to vault) | `notes/memos` |
| `PROCESS_FILES_AFTER_DATE` | No | Only process files created after this date (YYYY-MM-DD) | - |
| `OPENAI_WHISPER_MODEL` | No | OpenAI model for audio transcription | `whisper-1` |
| `OPENAI_CHAT_MODEL` | No | OpenAI model for summarization and title generation | `gpt-4o-mini` |

## Usage

Run the application:

```bash
python main.py
```

The application will:
1. Scan your Apple Voice Memos directory
2. Filter out already processed files and files before the cutoff date
3. Transcribe new audio files
4. Generate summaries and titles
5. Copy audio files to your Obsidian vault with descriptive names
6. Create markdown notes with transcriptions
7. Update or create daily notes with references

## Output Structure

### Memo Notes
Created in `{vault}/notes/memos/` with format:
```markdown
# AI-Generated Title

**Date:** 2024-01-15 14:30:00
**Audio:** [[attachments/20240115_143000_Short_Summary.m4a]]

## Summary
AI-generated 2-3 sentence summary of the content.

## Transcription
Full transcription of the audio memo...
```

### Daily Notes
Updated or created in `{vault}/diary/` with format:
```markdown
# 2024-01-15

## Voice Memos
- [[notes/memos/20240115_143000_Title]]
```

### Audio Files
Copied to `{vault}/attachments/` with naming pattern:
```
{timestamp}_{ai_generated_summary}.m4a
```

## How It Works

1. **Discovery**: Scans Apple Voice Memos directory for `.m4a` files
2. **Duplicate Detection**: Checks MD5 hashes against existing files in attachments folder
3. **Date Filtering**: Skips files created before the configured date (if set)
4. **Transcription**: Uses OpenAI Whisper API for speech-to-text
5. **Summarization**: GPT-4o-mini generates title and summary
6. **Organization**: Creates structured notes and updates daily entries

## Development

### Project Structure
```
memo-transcription-to-obsidian/
├── main.py                 # Main application code
├── pyproject.toml          # Python project configuration
├── mise.toml              # Environment management
├── .env                   # Environment variables (create from .env.example)
└── README.md              # This file
```

### Using mise for environment management

This project supports [mise](https://mise.jdx.dev/) for environment management:

```bash
mise install
```

## Troubleshooting

### Common Issues

**"OPENAI_API_KEY environment variable is not set"**
- Ensure your `.env` file contains a valid OpenAI API key

**"OBSIDIAN_VAULT_PATH does not exist"**
- Verify the path to your Obsidian vault is correct and absolute

**"Voice memos path does not exist"**
- This tool requires macOS with Apple Voice Memos installed
- Check that Voice Memos are stored in iCloud

**Empty transcriptions**
- Very short or silent audio files may result in empty transcriptions
- These files are automatically skipped

## Privacy & Security

- API keys are stored locally in `.env` (not committed to git)
- Audio files remain on your local machine
- Transcriptions are sent to OpenAI for processing
- Duplicate detection uses MD5 hashes of actual file content

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.