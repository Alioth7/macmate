import sys
content = "THOUGHT: 用户没有提供确切时间，我需要问他。\n你想要把会议定在什么时候？"

thought = ""
if "THOUGHT:" in content:
    parts = content.split("THOUGHT:", 1)
    if len(parts) > 1:
        thought_content = parts[1]
        # no ACTION, no ANSWER
        thought = thought_content.strip()

final_answer = content
if "THOUGHT:" in content:
    thought_parts = content.split("THOUGHT:", 1)[1]
    remaining = thought_parts.replace(thought, "", 1).strip()
    if remaining:
        final_answer = remaining
    else:
        final_answer = thought # fallback

print("THOUGHT:", repr(thought))
print("FINAL ANSWER:", repr(final_answer))
