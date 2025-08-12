import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import hashlib
import json

from openai import OpenAI


class Config:
    def __init__(self):
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.obsidian_vault_path = Path(os.environ.get("OBSIDIAN_VAULT_PATH", ""))
        self.attachments_folder = os.environ.get("OBSIDIAN_ATTACHMENTS_FOLDER", "attachments")
        self.diary_folder = os.environ.get("OBSIDIAN_DIARY_FOLDER", "diary")
        self.notes_folder = os.environ.get("OBSIDIAN_NOTES_FOLDER", "notes/memos")
        self.voice_memos_path = Path("/Users/guistiebler/Downloads/audios")
        
        # Parse date filter if provided
        date_filter_str = os.environ.get("PROCESS_FILES_AFTER_DATE")
        if date_filter_str:
            try:
                self.process_after_date = datetime.strptime(date_filter_str, "%Y-%m-%d")
                print(f"Processing files created after: {self.process_after_date.strftime('%Y-%m-%d')}")
            except ValueError:
                raise ValueError(f"PROCESS_FILES_AFTER_DATE '{date_filter_str}' must be in YYYY-MM-DD format")
        else:
            self.process_after_date = None
        
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        if not self.obsidian_vault_path or not self.obsidian_vault_path.exists():
            raise ValueError(f"OBSIDIAN_VAULT_PATH '{self.obsidian_vault_path}' does not exist")
        if not self.voice_memos_path.exists():
            raise ValueError(f"Voice memos path '{self.voice_memos_path}' does not exist")
    
    @property
    def attachments_path(self) -> Path:
        return self.obsidian_vault_path / self.attachments_folder
    
    @property
    def diary_path(self) -> Path:
        return self.obsidian_vault_path / self.diary_folder
    
    @property
    def notes_path(self) -> Path:
        return self.obsidian_vault_path / self.notes_folder


class MemoProcessor:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key)
        self._ensure_folders_exist()
        self._load_processed_files()
    
    def _ensure_folders_exist(self):
        self.config.attachments_path.mkdir(parents=True, exist_ok=True)
        self.config.diary_path.mkdir(parents=True, exist_ok=True)
        self.config.notes_path.mkdir(parents=True, exist_ok=True)
    
    def _load_processed_files(self):
        # Build hash set from existing files in attachments folder
        self.processed_files = set()
        
        # Scan all audio files in the attachments folder
        if self.config.attachments_path.exists():
            for audio_file in self.config.attachments_path.glob("*.m4a"):
                try:
                    file_hash = self._get_file_hash(audio_file)
                    self.processed_files.add(file_hash)
                except Exception as e:
                    print(f"Warning: Could not hash {audio_file.name}: {e}")
        
        print(f"Found {len(self.processed_files)} existing audio files in attachments folder")
    
    
    def _get_file_hash(self, file_path: Path) -> str:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def get_unprocessed_memos(self) -> List[Path]:
        memo_files = list(self.config.voice_memos_path.glob("*.m4a"))
        unprocessed = []
        
        for memo_file in memo_files:
            # Check date filter first
            if self.config.process_after_date:
                creation_date = self.get_file_creation_date(memo_file)
                if creation_date < self.config.process_after_date:
                    continue  # Skip files created before the cutoff date
            
            # Check if already processed
            file_hash = self._get_file_hash(memo_file)
            if file_hash not in self.processed_files:
                unprocessed.append(memo_file)
        
        return unprocessed
    
    def transcribe_audio(self, audio_file: Path) -> str:
        print(f"Transcribing {audio_file.name}...")
        try:
            with open(audio_file, "rb") as f:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="text"
                )
            return transcript
        except Exception as e:
            print(f"Error transcribing {audio_file.name}: {e}")
            raise
    
    def generate_summary_and_title(self, transcription: str) -> Dict[str, str]:
        print("Generating summary and title...")
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates concise summaries and titles for voice memos."
                    },
                    {
                        "role": "user",
                        "content": f"""Based on this transcription, provide:
1. A one-line summary (max 50 characters, suitable for a filename)
2. A longer summary (2-3 sentences)
3. A title for the note

Transcription:
{transcription}

Please respond in JSON format with keys: "filename_summary", "summary", "title"."""
                    }
                ],
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("No content in API response")
            result = json.loads(content)
            return result
        except Exception as e:
            print(f"Error generating summary: {e}")
            raise
    
    def sanitize_filename(self, filename: str) -> str:
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        filename = filename.strip()
        if not filename:
            filename = "untitled"
        return filename[:100]
    
    def copy_audio_file(self, source_file: Path, filename_summary: str) -> Path:
        sanitized_name = self.sanitize_filename(filename_summary)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{timestamp}_{sanitized_name}.m4a"
        destination = self.config.attachments_path / new_filename
        
        print(f"Copying audio file to {destination.name}...")
        shutil.copy2(source_file, destination)
        return destination
    
    def create_obsidian_note(self, title: str, summary: str, transcription: str, 
                           audio_file: Path, creation_date: datetime) -> Path:
        sanitized_title = self.sanitize_filename(title)
        timestamp = creation_date.strftime("%Y%m%d_%H%M%S")
        note_filename = f"{timestamp}_{sanitized_title}.md"
        note_path = self.config.notes_path / note_filename
        
        relative_audio_path = os.path.relpath(audio_file, self.config.obsidian_vault_path)
        
        note_content = f"""# {title}

**Date:** {creation_date.strftime("%Y-%m-%d %H:%M:%S")}
**Audio:** [[{relative_audio_path}]]

## Summary
{summary}

## Transcription
{transcription}

---
*Generated automatically from voice memo*
"""
        
        print(f"Creating note: {note_filename}...")
        with open(note_path, 'w', encoding='utf-8') as f:
            f.write(note_content)
        
        return note_path
    
    def update_daily_note(self, date: datetime, note_path: Path):
        daily_note_filename = date.strftime("%Y-%m-%d.md")
        daily_note_path = self.config.diary_path / daily_note_filename
        
        relative_note_path = os.path.relpath(note_path, self.config.obsidian_vault_path)
        note_link = f"- [[{relative_note_path.replace('.md', '')}]]"
        
        if daily_note_path.exists():
            print(f"Updating daily note: {daily_note_filename}...")
            with open(daily_note_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "## Voice Memos" not in content:
                content += "\n\n## Voice Memos\n"
            
            content += f"{note_link}\n"
            
            with open(daily_note_path, 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            print(f"Creating daily note: {daily_note_filename}...")
            content = f"""# {date.strftime("%Y-%m-%d")}

## Voice Memos
{note_link}
"""
            with open(daily_note_path, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def get_file_creation_date(self, file_path: Path) -> datetime:
        stat = file_path.stat()
        return datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_mtime)
    
    def process_memo(self, memo_file: Path):
        print(f"\n{'='*50}")
        print(f"Processing: {memo_file.name}")
        print(f"{'='*50}")
        
        try:
            creation_date = self.get_file_creation_date(memo_file)
            
            transcription = self.transcribe_audio(memo_file)
            
            if not transcription.strip():
                print("Empty transcription, skipping...")
                return
            
            summary_data = self.generate_summary_and_title(transcription)
            
            copied_audio = self.copy_audio_file(
                memo_file, 
                summary_data.get("filename_summary", "memo")
            )
            
            note_path = self.create_obsidian_note(
                summary_data.get("title", "Voice Memo"),
                summary_data.get("summary", ""),
                transcription,
                copied_audio,
                creation_date
            )
            
            self.update_daily_note(creation_date, note_path)
            
            # Add the hash to our in-memory set (for this session only)
            file_hash = self._get_file_hash(memo_file)
            self.processed_files.add(file_hash)
            
            print(f"✓ Successfully processed {memo_file.name}")
            
        except Exception as e:
            print(f"✗ Error processing {memo_file.name}: {e}")
    
    def process_all_memos(self):
        unprocessed = self.get_unprocessed_memos()
        
        if not unprocessed:
            print("No new memos to process.")
            return
        
        print(f"Found {len(unprocessed)} unprocessed memo(s)")
        
        for memo_file in unprocessed:
            self.process_memo(memo_file)
        
        print(f"\n{'='*50}")
        print(f"Processing complete! Processed {len(unprocessed)} memo(s)")
        print(f"{'='*50}")


def main():
    try:
        config = Config()
        processor = MemoProcessor(config)
        processor.process_all_memos()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease ensure the following environment variables are set:")
        print("  - OPENAI_API_KEY")
        print("  - OBSIDIAN_VAULT_PATH")
        print("  - OBSIDIAN_ATTACHMENTS_FOLDER (optional)")
        print("  - OBSIDIAN_DIARY_FOLDER (optional)")
        print("  - OBSIDIAN_NOTES_FOLDER (optional)")
        print("  - PROCESS_FILES_AFTER_DATE (optional, format: YYYY-MM-DD)")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()