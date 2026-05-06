import pandas as pd

linkedin_companies = ["ascendum", "infovision", "axi", "13brinda", "balbix", "infocepts", "tcs"]
custom_companies = ["appen", "thomson reuters", "alignerr"]

def linkedin_scraper(name):
    pass

def custom_scraper(name):
    if name.lower() == "appen":
        pass
    if name.lower() == "thomson reuters":
        pass
    if name.lower() == "alignerr":
        pass


def scrape(query):
    results = []

    try:
        query = query.lower()

        if query == "all":
            for comp in linkedin_companies:
                df = linkedin_scraper(comp)
                if df is not None:
                    results.append(df)

            for comp in custom_companies:
                df = custom_scraper(comp)
                if df is not None:
                    results.append(df)

        else:
            if query in linkedin_companies:
                df = linkedin_scraper(query)
            elif query in custom_companies:
                df = custom_scraper(query)
            else:
                raise ValueError(f"Unknown company: {query}")

            if df is not None:
                results.append(df)

        if not results:
            raise ValueError("No data collected")

        return pd.concat(results, ignore_index=True)

    except Exception as e:
        # You can log this later
        raise RuntimeError(f"Scraping failed: {str(e)}")

''' 
def scrape(query):
    data = [
        {"name": "Alice", "company": "TCS"},
        {"name": "Bob", "company": "Infosys"},
        {"name": "Charlie", "company": "Google"},
    ]

    df = pd.DataFrame(data)
    return df

'''
