import os
from pathlib import Path

class PromptManager:
    def __init__(self, prompts_dir: str = "config/prompts"):
        self.prompts_dir = Path(prompts_dir)
    
    def get_prompt(self, prompt_name: str) -> str:
        prompt_file = self.prompts_dir / f"{prompt_name}.txt"
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def get_prompt_with_params(self, prompt_name: str, **params) -> str:
        prompt = self.get_prompt(prompt_name)
        if prompt:
            return prompt.format(**params)
        return ""
