"""Download donor data from Salesforce, process and save to CSV."""

import os
import csv
import numpy as np
import pandas as pd
import sys

from datetime import date
from slacker import Slacker
from simple_salesforce import Salesforce
from simple_salesforce.api import SalesforceRefusedRequest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts import (
    SLACK_CHANNEL, SLACK_ACCESS_TOKEN, PROJECT_DIR, SALESFORCE_CREDENTIALS)

# The Contact and Opportunity tables have no relationship in Salesforce,
#   so there are two queries that get joined in Pandas.
donors_opportunities_query = """
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

donors_contacts_query = """
    SELECT AccountId, Name
    FROM Contact"""


def get_slack_connection(session=None):
    """Connect to Slack."""
    return Slacker(SLACK_ACCESS_TOKEN, session=session)


def query_salesforce(sf, query):
    """Get Salesforce data from SOQL query.

    Args:
        sf (:class:`simple_salesforce.api.Salesforce`): Salesforce connection.
        query (str): The SOQL query.

    Returns:
        dict: The response data.
    """
    try:
        return sf.query_all(query)
    except SalesforceRefusedRequest as e:  # Expired password
        slack = get_slack_connection()

        for error in e.content:
            message = error['message']

            slack.chat.post_message(
                SLACK_CHANNEL,
                text=f'ERROR: {message}. @channel')
        raise e


def create_opportunities_df(response):
    """Convert Salesforce query response to a Pandas DataFrame.

    Args:
        response (dict): The response from Salesforce.

    Returns:
        :class:`DataFrame`: Each Opportunity's amount, date and account ID.
    """
    data = [
        {'AMT': r['Amount'], 'DATE': r['CloseDate'], 'ACCOUNT': r['AccountId']}
        for r in response['records']]

    return pd.DataFrame(data)


def create_contacts_df(response):
    """Convert Salesforce query response to a Pandas DataFrame.

    Args:
        response (dict): The response from Salesforce.

    Returns:
        :class:`DataFrame`: Each Contact's name and Account ID.
    """
    data = [
        {'ACCOUNT': record['AccountId'], 'NAME': record['Name']}
        for record in response['records']]

    return pd.DataFrame(data)


def clean_opportunities_df(df):
    """Clean the Opportunities DataFrame.

    Fix data types and create the "YEAR" column.

    Args:
        df (:class:`DataFrame`): The raw Opportunities DataFrame.

    Returns:
        :class:`DataFrame`: Opportunities with cleaned values.
    """
    df['AMT'] = pd.to_numeric(df['AMT'], errors='coerce')
    df['AMT'] = df['AMT'].astype(int)

    df['DATE'] = pd.to_datetime(df['DATE'], format='%Y-%m-%d')

    df['YEAR'] = [d.year for d in df['DATE']]
    del df['DATE']

    return df


def build_series_no_serial_comma(names):
    """Build an AP style series (no serial/Oxford comma).

    Args:
        names (list): The names.

    Returns:
        str: The series. Ex. "John, Jane and Joe."
    """
    b = []

    if len(names) > 2:  # ['X', 'Y', 'Z']
        all_but_final_name = ', '.join(names[:-1])  # 'X, Y'
        b = [all_but_final_name, names[-1]]  # ['X, Y', 'Z']
    else:  # ['X', 'Y']
        b = names

    return ' and '.join(b)


def clean_contacts_df(df):
    """Clean the Contacts (donors) DataFrame.

    Combine contacts with the same Account into a single record.

    Args:
        df (:class:`DataFrame`): The raw Contacts (donors) DataFrame.

    Returns:
        :class:`DataFrame`: Contacts (donors) grouped by Accounts.
    """
    return df.groupby(['ACCOUNT'])['NAME'].apply(
        lambda x: build_series_no_serial_comma(x.tolist())).reset_index()


def merge_and_slice(opportunities_df, contacts_df):
    """Merge the two DataFrames and remove donations pledged for the future.

    Args:
        opportunities_df (:class:`DataFrame`): Opportunities (donations).
        contacts_df (:class:`DataFrame`): Contacts.

    Returns:
        :class:`DataFrame`: The Opportunities matched with their donors.
    """
    merged_df = pd.merge(opportunities_df, contacts_df, on='ACCOUNT')
    return merged_df.loc[merged_df['YEAR'] <= date.today().year]


def bin_donors_by_giving_level(df):
    """Apply giving-level labels.

    Args:
        df (:class:`DataFrame`): Summed donations for each donor.

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
        "<strong>Publisher's Circle\n$2,500-$4,999</strong>"]

    # right=False is exclusive of upper bound
    df['LEVEL'] = pd.cut(df['AMT'], bins, right=False, labels=labels)
    df['LASTNAME'] = df['NAME'].apply(lambda x: x.split(' ')[-1])

    # LEVEL is asc=False because categorical.
    df.sort_values(
        ['LEVEL', 'LASTNAME'], ascending=[False, True], inplace=True)

    df.reset_index(drop=True, inplace=True)

    return df


def write_levels_csv(df, year):
    """Write a CSV file containing donors and their giving levels.

    Args:
        df (:class:`DataFrame`): Donors and their giving levels.
        year (str): The year when these donations were given.
    """
    csv_out = '{0}/data/{1}.csv'.format(PROJECT_DIR, year)

    if not os.path.exists(os.path.dirname(csv_out)):
        os.makedirs(os.path.dirname(csv_out))

    with open(csv_out, 'w') as out_file:
        csvwriter = csv.writer(out_file, quoting=csv.QUOTE_ALL)

        current_level = ''
        for donor in df[['NAME', 'LEVEL']].itertuples():
            if current_level != donor.LEVEL:
                current_level = donor.LEVEL
                csvwriter.writerow([donor.LEVEL])

            csvwriter.writerow([donor.NAME])


def get_donations_by_year(df):
    """Sum donations by year and donor.

    Args:
        df (:class:`DataFrame`): All donations across all years.

    Returns:
        :class:`DataFrame`: Donations summed by each year.
    """
    return df.groupby(['YEAR', 'ACCOUNT', 'NAME'])['AMT'].sum().reset_index()


def get_donations_by_donor(df):
    """Sum donations by donor across all years.

    Args:
        df (:class:`DataFrame`): All donations across all years.

    Returns:
        :class:`DataFrame`: All-time donations for each donor.
    """
    sum_by_person = df.groupby(['ACCOUNT', 'NAME'])['AMT'].sum().reset_index()
    sum_by_person['YEAR'] = 'all-time'

    return sum_by_person


def get_salesforce_connection(session=None):
    """Connect to Salesforce."""
    return Salesforce(
        username=SALESFORCE_CREDENTIALS['USERNAME'],
        password=SALESFORCE_CREDENTIALS['PASSWORD'],
        security_token=SALESFORCE_CREDENTIALS['SECURITY_TOKEN'],
        session=session)


def process_annual_donations(df):
    """Sort each donor's annual donations into giving levels.

    Write out each year's data to a CSV file.

    Args:
        df (:class:`DataFrame`): Donations summed by year.
    """
    for year in range(df['YEAR'].min(), df['YEAR'].max() + 1):
        levels_df = bin_donors_by_giving_level(df)
        write_levels_csv(levels_df[levels_df['YEAR'] == year], str(year))


def get_donations():
    """Get all donations from all donors across all years.

    Returns:
        :class:`DataFrame`: All donations.
    """
    sf = get_salesforce_connection()

    opportunities = query_salesforce(sf, donors_opportunities_query)
    contacts = query_salesforce(sf, donors_contacts_query)

    opportunities_df = create_opportunities_df(opportunities)
    contacts_df = create_contacts_df(contacts)

    cleaned_opportunities_df = clean_opportunities_df(opportunities_df)
    cleaned_contacts_df = clean_contacts_df(contacts_df)

    return merge_and_slice(cleaned_opportunities_df, cleaned_contacts_df)


def main():
    """Download donor data from Salesforce, process and save to CSV.

    Save a CSV file for each year's donations and for all-time donations.
    """
    donations_df = get_donations()

    # Process all-time donations
    alltime_donations_df = get_donations_by_donor(donations_df)
    giving_levels_df = bin_donors_by_giving_level(alltime_donations_df)
    write_levels_csv(giving_levels_df, 'all-time-donations')

    # Process annual donations
    annual_donations_df = get_donations_by_year(donations_df)
    process_annual_donations(annual_donations_df)


if __name__ == "__main__":
    main()
