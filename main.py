import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import hashlib
import json

from openai import OpenAI
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


console = Console()


class Config:
    def __init__(self):
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.obsidian_vault_path = Path(os.environ.get("OBSIDIAN_VAULT_PATH", ""))
        self.attachments_folder = os.environ.get("OBSIDIAN_ATTACHMENTS_FOLDER", "attachments")
        self.diary_folder = os.environ.get("OBSIDIAN_DIARY_FOLDER", "diary")
        self.notes_folder = os.environ.get("OBSIDIAN_NOTES_FOLDER", "notes/memos")
        self.voice_memos_path = Path("/Users/guistiebler/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings")
        
        # Parse date filter if provided
        date_filter_str = os.environ.get("PROCESS_FILES_AFTER_DATE")
        if date_filter_str:
            try:
                self.process_after_date = datetime.strptime(date_filter_str, "%Y-%m-%d")
                console.print(f"[cyan]Processing files created after:[/cyan] {self.process_after_date.strftime('%Y-%m-%d')}")
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
            with console.status("[bold green]Scanning existing audio files...", spinner="dots"):
                for audio_file in self.config.attachments_path.glob("*.m4a"):
                    try:
                        file_hash = self._get_file_hash(audio_file)
                        self.processed_files.add(file_hash)
                    except Exception as e:
                        console.print(f"[yellow]Warning:[/yellow] Could not hash {audio_file.name}: {e}")
        
        console.print(f"[green]✓[/green] Found [bold]{len(self.processed_files)}[/bold] existing audio files in attachments folder")
    
    def _get_file_hash(self, file_path: Path) -> str:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def get_unprocessed_memos(self) -> List[Path]:
        memo_files = list(self.config.voice_memos_path.glob("*.m4a"))
        unprocessed = []
        
        with console.status("[bold green]Filtering voice memos...", spinner="dots"):
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
        with console.status(f"[bold blue]Transcribing {audio_file.name}...[/bold blue]", spinner="dots"):
            try:
                with open(audio_file, "rb") as f:
                    transcript = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        response_format="text"
                    )
                return transcript
            except Exception as e:
                console.print(f"[red]Error transcribing {audio_file.name}: {e}[/red]")
                raise
    
    def generate_summary_and_title(self, transcription: str) -> Dict[str, str]:
        with console.status("[bold blue]Generating summary and title...[/bold blue]", spinner="dots"):
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
                console.print(f"[red]Error generating summary: {e}[/red]")
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
        
        with console.status("[bold cyan]Copying audio file...", spinner="dots"):
            shutil.copy2(source_file, destination)
        
        console.print(f"  [green]✓[/green] Audio saved as: [italic]{new_filename}[/italic]")
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
![[{relative_audio_path}]]

## Summary
{summary}

## Transcription
{transcription}

---
*Generated automatically from voice memo*
"""
        
        with console.status("[bold cyan]Creating note...", spinner="dots"):
            with open(note_path, 'w', encoding='utf-8') as f:
                f.write(note_content)
        
        console.print(f"  [green]✓[/green] Note created: [italic]{note_filename}[/italic]")
        return note_path
    
    def update_daily_note(self, date: datetime, note_path: Path):
        daily_note_filename = date.strftime("%Y-%m-%d.md")
        daily_note_path = self.config.diary_path / daily_note_filename
        
        relative_note_path = os.path.relpath(note_path, self.config.obsidian_vault_path)
        note_link = f"- [[{relative_note_path.replace('.md', '')}]]"
        
        with console.status("[bold cyan]Updating daily note...", spinner="dots"):
            if daily_note_path.exists():
                with open(daily_note_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if "## Voice Memos" not in content:
                    content += "\n\n## Voice Memos\n"
                
                content += f"{note_link}\n"
                
                with open(daily_note_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                console.print(f"  [green]✓[/green] Updated daily note: [italic]{daily_note_filename}[/italic]")
            else:
                content = f"""# {date.strftime("%Y-%m-%d")}

## Voice Memos
{note_link}
"""
                with open(daily_note_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                console.print(f"  [green]✓[/green] Created daily note: [italic]{daily_note_filename}[/italic]")
    
    def get_file_creation_date(self, file_path: Path) -> datetime:
        stat = file_path.stat()
        return datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_mtime)
    
    def process_memo(self, memo_file: Path, index: int, total: int):
        panel = Panel(
            f"[bold]Processing:[/bold] {memo_file.name}\n[dim]({index}/{total})[/dim]",
            style="bright_blue",
            expand=False
        )
        console.print(panel)
        
        try:
            creation_date = self.get_file_creation_date(memo_file)
            
            transcription = self.transcribe_audio(memo_file)
            
            if not transcription.strip():
                console.print("[yellow]  ⚠ Empty transcription, skipping...[/yellow]")
                return
            
            summary_data = self.generate_summary_and_title(transcription)
            
            # Display summary info
            summary_table = Table(show_header=False, box=None, padding=(0, 1))
            summary_table.add_column(style="bold cyan", width=12)
            summary_table.add_column()
            summary_table.add_row("Title:", summary_data.get("title", "Voice Memo"))
            summary_table.add_row("Summary:", Text(summary_data.get("summary", "")[:100] + "...", style="italic"))
            console.print(summary_table)
            
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
            
            console.print(f"[bold green]✓ Successfully processed {memo_file.name}[/bold green]\n")
            
        except Exception as e:
            console.print(f"[bold red]✗ Error processing {memo_file.name}: {e}[/bold red]\n")
    
    def process_all_memos(self):
        console.print(Panel.fit(
            "[bold cyan]Voice Memo Transcription to Obsidian[/bold cyan]",
            style="bright_blue"
        ))
        
        unprocessed = self.get_unprocessed_memos()
        
        if not unprocessed:
            console.print("[yellow]No new memos to process.[/yellow]")
            return
        
        console.print(f"\n[bold green]Found {len(unprocessed)} unprocessed memo(s)[/bold green]\n")
        
        for index, memo_file in enumerate(unprocessed, 1):
            self.process_memo(memo_file, index, len(unprocessed))
        
        # Summary table
        summary = Table(title="Processing Complete", style="green")
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="bold")
        summary.add_row("Memos Processed", str(len(unprocessed)))
        summary.add_row("Total Existing Files", str(len(self.processed_files)))
        
        console.print("\n")
        console.print(summary)


def main():
    try:
        config = Config()
        processor = MemoProcessor(config)
        processor.process_all_memos()
    except ValueError as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        console.print("\n[yellow]Please ensure the following environment variables are set:[/yellow]")
        console.print("  • OPENAI_API_KEY")
        console.print("  • OBSIDIAN_VAULT_PATH")
        console.print("  • OBSIDIAN_ATTACHMENTS_FOLDER (optional)")
        console.print("  • OBSIDIAN_DIARY_FOLDER (optional)")
        console.print("  • OBSIDIAN_NOTES_FOLDER (optional)")
        console.print("  • PROCESS_FILES_AFTER_DATE (optional, format: YYYY-MM-DD)")
    except KeyboardInterrupt:
        console.print("\n[yellow]Process interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        console.print_exception()


if __name__ == "__main__":
    main()