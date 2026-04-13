import requests

class BiologicalDataIngestor:
    def __init__(self, use_env_proxy=False, timeout=30):
        # The base URL for the new ClinicalTrials.gov API v2
        self.ctg_base_url = "https://clinicaltrials.gov/api/v2/studies"
        self.timeout = timeout
        self.session = requests.Session()

        # Some local environments export broken proxy variables. By default
        # we bypass those so direct API calls still work.
        self.session.trust_env = use_env_proxy

    def fetch_trial_data(self, nct_id):
        """Scrapes ClinicalTrials.gov for specific trial features."""

        # 1. We build the exact web address for the specific trial
        url = f"{self.ctg_base_url}/{nct_id}"
        print(f"Connecting to: {url}...")

        try:
            # 2. We 'GET' the data from the internet
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            print(f"Network error while fetching data: {exc}")
            return None

        # 3. HTTP Status 200 means "Success OK".
        if response.status_code == 200:
            # The data comes back as JSON (a nested dictionary)
            return response.json()

        if response.status_code == 404:
            print(
                f"Study '{nct_id}' was not found. "
                "Double-check the NCT ID."
            )
            return None

        print(f"Failed to fetch data. Error Code: {response.status_code}")
        return None

# --- Testing Our Detective ---
if __name__ == '__main__':
    # Instantiate the class
    ingestor = BiologicalDataIngestor()

    # Use a known-valid example study ID for the demo run.
    test_nct_id = "NCT00276653"

    # Run our function
    trial_data = ingestor.fetch_trial_data(test_nct_id)

    # If it worked, let's drill into the dictionary and print the title
    if trial_data:
        print("\nSuccess! We intercepted the data.")
        # JSON data is heavily nested. We are digging down to find the title.
        title = trial_data['protocolSection']['identificationModule']['briefTitle']
        print(f"Trial Title: {title}")
