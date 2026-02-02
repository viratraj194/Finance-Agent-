from capabilities.ipo_financials import analyze_financials

sample_text = [
    "The company reported revenue of ₹1,819.80 crore in FY25.",
    "Net profit stood at ₹21.04 crore in FY25.",
    "Total debt is ₹1,150 crore."
]

print(analyze_financials(sample_text))
