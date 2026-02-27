from pathlib import Path

def load_agent_prompt(role: str) -> str:
    """
    Load the base prompt and the corresponding SKILL.md for a given role,
    and combine them into a single system prompt.
    """
    agents_dir = Path(__file__).parent
    base_prompt_path = agents_dir.parent.parent / "prompts" / f"{role}.md"
    
    skill_path_map = {
        "account_planner": "account_planning",
        "brand_strategist": "brand_strategy",
        "creative_director": "creative_direction",
        "presentation_designer": "presentation_design",
    }
    
    base_prompt = ""
    if base_prompt_path.exists():
        base_prompt = base_prompt_path.read_text(encoding="utf-8")
        
    skill_dir_name = skill_path_map.get(role)
    if skill_dir_name:
        skill_path = agents_dir / "skills" / skill_dir_name / "SKILL.md"
        if skill_path.exists():
            skill_content = skill_path.read_text(encoding="utf-8")
            # Combine the base prompt and the skill guideline
            return f"{base_prompt}\n\n---\n\n{skill_content}"
            
    return base_prompt
