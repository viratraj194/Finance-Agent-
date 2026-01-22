import requests
from bs4 import BeautifulSoup

def get_ipo_analysis(target_company):
    headers = {'User-Agent': 'Mozilla/5.0'}
    # 2026 Mainboard List
    base_url = "https://www.chittorgarh.com/report/mainboard-ipo-list-in-india-bse-nse/83/"
    
    try:
        # 1. Find the link for the company
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        ipo_link = None
        for a in soup.find_all('a', href=True):
            if target_company.lower() in a.text.lower() and "/ipo/" in a['href']:
                ipo_link = a['href'] if a['href'].startswith("http") else "https://www.chittorgarh.com" + a['href']
                break
        
        if not ipo_link:
            return f"❌ Could not find IPO link for {target_company}"

        # 2. Scrape the IPO page
        page = requests.get(ipo_link, headers=headers)
        ps = BeautifulSoup(page.text, 'html.parser')
        results = {"Company": target_company.upper(), "URL": ipo_link}

        # 3. Find the Financial Table
        # We look for the table that contains "Profit After Tax"
        fin_table = None
        for table in ps.find_all('table'):
            if "Profit After Tax" in table.get_text():
                fin_table = table
                break
        
        if fin_table:
            rows = fin_table.find_all('tr')
            # The first row (headers) tells us the years
            headers_row = [th.text.strip() for th in rows[0].find_all(['th', 'td'])]
            
            # Find which column index has the latest year (2025 or 2026)
            latest_col_idx = 1 # Default to first data column
            for i, h in enumerate(headers_row):
                if "2025" in h or "2026" in h:
                    latest_col_idx = i
                    results["Data Period"] = h
                    break

            for row in rows:
                cols = row.find_all(['td', 'th'])
                label = cols[0].text.strip()
                if "Total Revenue" in label or "Total Income" in label:
                    results["Revenue"] = f"₹{cols[latest_col_idx].text.strip()} Cr"
                if "Profit After Tax" in label or "PAT" in label:
                    val = cols[latest_col_idx].text.strip()
                    results["Net Profit"] = f"₹{val} Cr"
                    # Set sentiment based on latest profit
                    results["Sentiment"] = "🚀 Profitable / Turnaround" if "-" not in val else "⚠️ Loss Making"

        # 4. Get Price Band
        for row in ps.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 2:
                txt = cells[0].text.strip()
                if "Price Band" in txt: results["Price"] = cells[1].text.strip()
                if "Issue Size" in txt: results["Size"] = cells[1].text.strip()

        return results

    except Exception as e:
        return f"❌ Error: {e}"

# --- TEST ---
if __name__ == "__main__":
    data = get_ipo_analysis("Shadowfax")
    print("\n✅ FINAL REPORT:")
    for k, v in data.items():
        print(f"🔹 {k}: {v}")