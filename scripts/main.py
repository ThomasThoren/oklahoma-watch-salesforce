"""Download donor data from Salesforce, process and save to CSV."""

from datetime import date
import os
import csv
import sys

import numpy as np
import pandas as pd
from slacker import Slacker
from simple_salesforce import Salesforce
from simple_salesforce.api import SalesforceRefusedRequest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts import SLACK_CHANNEL, SLACK_ACCESS_TOKEN, PROJECT_DIR, SALESFORCE_CREDENTIALS  # pylint: disable=wrong-import-position

# The Contact and Opportunity tables have no relationship in Salesforce, so there are two queries that get joined in Pandas.
DONORS_OPPORTUNITIES_QUERY = """
    SELECT Amount, CloseDate, AccountId
    FROM Opportunity
    WHERE AccountId IN (
        SELECT Id
        FROM Account
        WHERE Type IN ('Household', 'Foundation')
    )
    AND StageName IN ('Closed Won', 'Invoiced', 'Pledged')
    AND Amount != NULL
    AND npsp__Primary_Contact__c != NULL
    AND Amount > 0"""

DONORS_CONTACTS_QUERY = """
    SELECT AccountId, Name
    FROM Contact"""


def get_slack_connection():
    """Connect to Slack."""
    return Slacker(SLACK_ACCESS_TOKEN, session=None)


def query_salesforce(salesforce_connection, soql_query: str) -> dict:
    """Get Salesforce data from SOQL query.

    Args:
        salesforce_connection (:class:`simple_salesforce.api.Salesforce`): Salesforce connection.
    """
    try:
        response = salesforce_connection.query_all(soql_query)
    except SalesforceRefusedRequest as err:  # Expired password
        slack = get_slack_connection()
        for error in err.content:
            message = error['message']
            slack.chat.post_message(SLACK_CHANNEL, text=f'ERROR: {message}. @channel')

        raise

    return response


def create_opportunities_dataframe(response: dict) -> pd.DataFrame:
    """Convert Salesforce query response to a dataframe with each Opportunity's amount, data, and Account ID."""
    data = [{'AMT': r['Amount'], 'DATE': r['CloseDate'], 'ACCOUNT': r['AccountId']} for r in response['records']]
    return pd.DataFrame(data)


def create_contacts_dataframe(response: dict) -> pd.DataFrame:
    """Convert Salesforce query response to a dataframe with each contact's name and Account ID."""
    data = [{'ACCOUNT': record['AccountId'], 'NAME': record['Name']} for record in response['records']]
    return pd.DataFrame(data)


def clean_opportunities_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw Opportunities DataFrame into a cleaned dataframe.

    Fix data types and create the "YEAR" column.
    """
    dataframe['AMT'] = pd.to_numeric(dataframe['AMT'], errors='coerce')
    dataframe['AMT'] = dataframe['AMT'].astype(int)
    dataframe['DATE'] = pd.to_datetime(dataframe['DATE'], format='%Y-%m-%d')
    dataframe['YEAR'] = [d.year for d in dataframe['DATE']]
    del dataframe['DATE']
    return dataframe


def build_series_no_serial_comma(names: list) -> str:
    """Build an AP style series (no serial comma) string from a list of values."""
    all_but_final_and_final = []

    if len(names) > 2:  # ['X', 'Y', 'Z']
        all_but_final_name = ', '.join(names[:-1])  # 'X, Y'
        all_but_final_and_final = [all_but_final_name, names[-1]]  # ['X, Y', 'Z']
    else:  # ['X', 'Y']
        all_but_final_and_final = names

    return ' and '.join(all_but_final_and_final)


def clean_contacts_dataframe(dataframe: pd.DataFrame):
    """Clean the Contacts (donors) DataFrame.

    Combine contacts with the same Account into a single record.

    Args:
        dataframe (:class:`DataFrame`): The raw Contacts (donors) DataFrame.

    Returns:
        :class:`DataFrame`: Contacts (donors) grouped by Accounts.
    """
    return dataframe.groupby(['ACCOUNT'])['NAME'].apply(lambda x: build_series_no_serial_comma(x.tolist())).reset_index()


def merge_and_slice(opportunities_dataframe, contacts_dataframe):
    """Merge the two DataFrames and remove donations pledged for the future.

    Args:
        opportunities_dataframe (:class:`DataFrame`): Opportunities (donations).
        contacts_dataframe (:class:`DataFrame`): Contacts.

    Returns:
        :class:`DataFrame`: The Opportunities matched with their donors.
    """
    merged_dataframe = pd.merge(opportunities_dataframe, contacts_dataframe, on='ACCOUNT')
    return merged_dataframe.loc[merged_dataframe['YEAR'] <= date.today().year]


def bin_donors_by_giving_level(dataframe: pd.DataFrame):
    """Apply giving-level labels.

    Args:
        dataframe (:class:`DataFrame`): Summed donations for each donor.

    Returns:
        :class:`DataFrame`: Donations and their corresponding giving-level
            labels, sorted first by giving level (descending) and second by
            last name (ascending).
    """
    bins = [0, 50, 100, 250, 500, 1000, 2500, np.inf]

    labels = [
        "<strong>Friend\n$1-$49</strong>",
        "<strong>Supporter\n$50-$99</strong>",
        "<strong>Patron\n$100-$249</strong>",
        "<strong>Champion Level\n$250-$499</strong>",
        "<strong>Ambassador\n$500-$999</strong>",
        "<strong>Editor's Circle\n$1,000-$2,499</strong>",
        "<strong>Publisher's Circle\n$2,500-$4,999</strong>"
    ]

    # right=False is exclusive of upper bound
    dataframe['LEVEL'] = pd.cut(dataframe['AMT'], bins, right=False, labels=labels)
    dataframe['LASTNAME'] = dataframe['NAME'].apply(lambda x: x.split(' ')[-1])

    # LEVEL is asc=False because categorical.
    dataframe.sort_values(['LEVEL', 'LASTNAME'], ascending=[False, True], inplace=True)

    dataframe.reset_index(drop=True, inplace=True)

    return dataframe


def write_levels_csv(dataframe: pd.DataFrame, file_name: str):
    """Write a CSV file containing donors and their giving levels."""
    csv_out = '{0}/data/{1}.csv'.format(PROJECT_DIR, file_name)

    if not os.path.exists(os.path.dirname(csv_out)):
        os.makedirs(os.path.dirname(csv_out))

    with open(csv_out, 'w') as out_file:
        csvwriter = csv.writer(out_file, quoting=csv.QUOTE_ALL)

        current_level = ''
        for donor in dataframe[['NAME', 'LEVEL']].itertuples():
            if current_level != donor.LEVEL:
                current_level = donor.LEVEL
                csvwriter.writerow([donor.LEVEL])

            csvwriter.writerow([donor.NAME])


def get_donations_by_year(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Sum all donations by year and donor."""
    return dataframe.groupby(['YEAR', 'ACCOUNT', 'NAME'])['AMT'].sum().reset_index()


def get_donations_by_donor(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Sum all donations by donor (across all years)."""
    sum_by_person = dataframe.groupby(['ACCOUNT', 'NAME'])['AMT'].sum().reset_index()
    sum_by_person['YEAR'] = 'all-time'
    return sum_by_person


def get_salesforce_connection(session=None):
    """Connect to Salesforce."""
    return Salesforce(
        username=SALESFORCE_CREDENTIALS['USERNAME'],
        password=SALESFORCE_CREDENTIALS['PASSWORD'],
        security_token=SALESFORCE_CREDENTIALS['SECURITY_TOKEN'],
        session=session
    )


def process_annual_donations(dataframe: pd.DataFrame):
    """Sort each donor's annual donations into giving levels.

    Write out each year's data to a CSV file.
    """
    for year in range(dataframe['YEAR'].min(), dataframe['YEAR'].max() + 1):
        levels_dataframe = bin_donors_by_giving_level(dataframe)
        write_levels_csv(levels_dataframe[levels_dataframe['YEAR'] == year], str(year))


def get_donations() -> pd.DataFrame:
    """Get all donations from all donors across all years.

    Returns:
        :class:`DataFrame`: All donations.
    """
    salesforce_connection = get_salesforce_connection()

    opportunities = query_salesforce(salesforce_connection, DONORS_OPPORTUNITIES_QUERY)
    contacts = query_salesforce(salesforce_connection, DONORS_CONTACTS_QUERY)

    opportunities_dataframe = create_opportunities_dataframe(opportunities)
    contacts_dataframe = create_contacts_dataframe(contacts)

    cleaned_opportunities_dataframe = clean_opportunities_dataframe(opportunities_dataframe)
    cleaned_contacts_dataframe = clean_contacts_dataframe(contacts_dataframe)

    return merge_and_slice(cleaned_opportunities_dataframe, cleaned_contacts_dataframe)


def main():
    """Download donor data from Salesforce, process and save to CSV.

    Save a CSV file for each year's donations and for all-time donations.
    """
    donations_dataframe = get_donations()

    # Process all-time donations
    alltime_donations_dataframe = get_donations_by_donor(donations_dataframe)
    giving_levels_dataframe = bin_donors_by_giving_level(alltime_donations_dataframe)
    write_levels_csv(giving_levels_dataframe, 'all-time-donations')

    # Process annual donations
    annual_donations_dataframe = get_donations_by_year(donations_dataframe)
    process_annual_donations(annual_donations_dataframe)


if __name__ == "__main__":
    main()
