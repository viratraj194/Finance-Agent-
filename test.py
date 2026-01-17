from capabilities.attention import get_social_attention

data = get_social_attention("hdfc bank")

print(data["status"])
print(data["analysis_input"])
