"""Unit tests for scripts/initialize.py."""

import os
import pandas as pd
import requests
import sys
import unittest

from mock import patch, call
from simple_salesforce.api import SalesforceRefusedRequest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from scripts import main


class TestMain(unittest.TestCase):
    """Test cases for scripts/main.py."""

    @patch('simple_salesforce.Salesforce')
    def test_query_salesforce(self, mock_sf):
        """Test query_salesforce()."""
        mock_sf.query_all.return_value = 'data'
        query = 'query'

        returned = main.query_salesforce(mock_sf, query)

        self.assertEqual(returned, 'data')

    @patch('scripts.main.Slacker')
    @patch('simple_salesforce.Salesforce')
    def test_query_salesforce_expired_password(self, mock_sf, mock_slack):
        """Test query_salesforce() when password has expired."""
        query = 'query'
        mock_sf.query_all.side_effect = SalesforceRefusedRequest(
            'url', 'status', 'resource_name', [{'message': 'Error'}])

        with self.assertRaises(SalesforceRefusedRequest):
            main.query_salesforce(mock_sf, query)

        assert mock_slack.called

    def test_create_opportunities_df(self):
        """Test create_opportunities_df()."""
        response = {'records': [
            {'Amount': '10', 'CloseDate': '2016', 'AccountId': '1', 'X': 'Y'},
            {'Amount': '20', 'CloseDate': '2015', 'AccountId': '2', 'X': 'Z'}]}

        actual = main.create_opportunities_df(response)
        expected = pd.DataFrame.from_dict([
            {'AMT': '10', 'DATE': '2016', 'ACCOUNT': '1'},
            {'AMT': '20', 'DATE': '2015', 'ACCOUNT': '2'}])

        self.assertTrue(actual.equals(expected))

    def test_create_contacts_df(self):
        """Test create_contacts_df()."""
        response = {'records': [
            {'Name': 'John', 'AccountId': '1', 'X': 'Y'},
            {'Name': 'Jane', 'AccountId': '2', 'X': 'Z'}]}

        actual = main.create_contacts_df(response)
        expected = pd.DataFrame.from_dict([{'NAME': 'John', 'ACCOUNT': '1'},
                                           {'NAME': 'Jane', 'ACCOUNT': '2'}])

        self.assertTrue(actual.equals(expected))

    @patch('scripts.main.build_series_no_serial_comma')
    def test_clean_opportunities_df(self, mock_build_series):
        """Test clean_opportunities_df()."""
        d = [{'AMT': '1', 'DATE': '2016-10-31', 'ACCOUNT': '1'},
             {'AMT': 2, 'DATE': '2015-12-25', 'ACCOUNT': '2'}]
        df = pd.DataFrame.from_dict(d)

        actual = main.clean_opportunities_df(df)
        expected = pd.DataFrame.from_dict([
            {'AMT': 1, 'YEAR': 2016, 'ACCOUNT': '1'},
            {'AMT': 2, 'YEAR': 2015, 'ACCOUNT': '2'}])

        self.assertTrue(actual.equals(expected))

    @patch('scripts.main.build_series_no_serial_comma')
    def test_clean_contacts_df(self, mock_build_series):
        """Test clean_contacts_df()."""
        mock_build_series.return_value = 'John, Jane and Jim'

        d = [{'ACCOUNT': '1', 'NAME': 'John'},
             {'ACCOUNT': '1', 'NAME': 'Jane'},
             {'ACCOUNT': '1', 'NAME': 'Jim'}]
        df = pd.DataFrame.from_dict(d)

        actual = main.clean_contacts_df(df)
        expected = pd.DataFrame.from_dict(
            [{'ACCOUNT': '1', 'NAME': 'John, Jane and Jim'}])

        self.assertTrue(actual.equals(expected))

    def test_build_series_no_serial_comma_empty(self):
        """Test build_series_no_serial_comma() with empty list."""
        name_series = main.build_series_no_serial_comma([])
        self.assertEqual(name_series, "")

    def test_build_series_no_serial_comma_single_name(self):
        """Test build_series_no_serial_comma() with a single name."""
        name_series = main.build_series_no_serial_comma(["John"])
        self.assertEqual(name_series, "John")

    def test_build_series_no_serial_comma_two_names(self):
        """Test build_series_no_serial_comma() with two names."""
        name_series = main.build_series_no_serial_comma(["John", "Jane"])
        self.assertEqual(name_series, "John and Jane")

    def test_build_series_no_serial_comma_three_names(self):
        """Test build_series_no_serial_comma() with three names."""
        series = main.build_series_no_serial_comma(["John", "Jane", "Jim"])
        self.assertEqual(series, "John, Jane and Jim")

    def test_merge_and_slice(self):
        """Test merge_and_slice()."""
        opps_df = pd.DataFrame.from_dict([
            {'ACCOUNT': '1', 'AMT': 10, 'YEAR': 2015},
            {'ACCOUNT': '1', 'AMT': 20, 'YEAR': 2016},
            {'ACCOUNT': '2', 'AMT': 30, 'YEAR': 2017}])

        contacts_df = pd.DataFrame.from_dict([
            {'ACCOUNT': '1', 'NAME': 'John and Jan'},
            {'ACCOUNT': '2', 'NAME': 'Jim'}])

        actual = main.merge_and_slice(opps_df, contacts_df).sort_index(axis=1)

        d = [{'ACCOUNT': '1', 'NAME': 'John and Jan', 'AMT': 10, 'YEAR': 2015},
             {'ACCOUNT': '1', 'NAME': 'John and Jan', 'AMT': 20, 'YEAR': 2016},
             {'ACCOUNT': '2', 'NAME': 'Jim', 'AMT': 30, 'YEAR': 2017}]
        expected = pd.DataFrame.from_dict(d).sort_index(axis=1)

        self.assertTrue(actual.equals(expected))

    def test_bin_donors_by_giving_level(self):
        """Test bin_donors_by_giving_level()."""
        df = pd.DataFrame.from_dict([{'AMT': 0, 'NAME': 'John M Doe'},
                                     {'AMT': 50, 'NAME': 'Jane Doe'},
                                     {'AMT': 100, 'NAME': 'John Deere'},
                                     {'AMT': 250, 'NAME': 'Joe Doe'},
                                     {'AMT': 500, 'NAME': 'Jon Doe'},
                                     {'AMT': 1000, 'NAME': 'Jan Doe'},
                                     {'AMT': 5000, 'NAME': 'Jim'}])

        actual = main.bin_donors_by_giving_level(df).sort_index(axis=1)

        d = [{'AMT': 5000, 'NAME': 'Jim', 'LASTNAME': 'Jim',
              'LEVEL': "<strong>Publisher's Circle\n$2,500-$4,999</strong>"},
             {'AMT': 1000, 'NAME': 'Jan Doe', 'LASTNAME': 'Doe',
              'LEVEL': "<strong>Editor's Circle\n$1,000-$2,499</strong>"},
             {'AMT': 500, 'NAME': 'Jon Doe', 'LASTNAME': 'Doe',
              'LEVEL': '<strong>Ambassador\n$500-$999</strong>'},
             {'AMT': 250, 'NAME': 'Joe Doe', 'LASTNAME': 'Doe',
              'LEVEL': '<strong>Champion Level\n$250-$499</strong>'},
             {'AMT': 100, 'NAME': 'John Deere', 'LASTNAME': 'Deere',
              'LEVEL': '<strong>Patron\n$100-$249</strong>'},
             {'AMT': 50, 'NAME': 'Jane Doe', 'LASTNAME': 'Doe',
              'LEVEL': '<strong>Supporter\n$50-$99</strong>'},
             {'AMT': 0, 'NAME': 'John M Doe', 'LASTNAME': 'Doe',
              'LEVEL': '<strong>Friend\n$1-$49</strong>'}]
        expected = pd.DataFrame.from_dict(d).astype(
            {'LEVEL': 'category'}).sort_index(axis=1)

        self.assertTrue(actual.equals(expected))

    @patch('scripts.main.csv.writer')
    def test_write_levels_csv(self, mock_csv):
        """Test write_levels_csv()."""
        df = pd.DataFrame.from_dict([
            {'NAME': 'John Doe', 'LEVEL': "Publisher's Circle"},
            {'NAME': 'Jane Doe', 'LEVEL': "Publisher's Circle"},
            {'NAME': 'John Deere', 'LEVEL': "Editor's Circle"}])

        main.write_levels_csv(df, '2016')

        mock_csv_calls = [
            call(["Publisher's Circle"]),
            call(["John Doe"]),
            call(["Jane Doe"]),
            call(["Editor's Circle"]),
            call(["John Deere"])]

        self.assertEqual(
            mock_csv.return_value.writerow.call_args_list, mock_csv_calls)

    def test_get_donations_by_year(self):
        """Test get_donations_by_year()."""
        df = pd.DataFrame.from_dict([
            {'YEAR': 2015, 'ACCOUNT': '1', 'AMT': 500, 'NAME': 'John Doe'},
            {'YEAR': 2015, 'ACCOUNT': '1', 'AMT': 1000, 'NAME': 'John Doe'},
            {'YEAR': 2016, 'ACCOUNT': '1', 'AMT': 200, 'NAME': 'John Doe'},
            {'YEAR': 2017, 'ACCOUNT': '2', 'AMT': 500, 'NAME': 'Jane Doe'},
            {'YEAR': 2017, 'ACCOUNT': '2', 'AMT': 500, 'NAME': 'Jane Doe'}])

        returned = main.get_donations_by_year(df).sort_index(axis=1)
        expected = pd.DataFrame.from_dict([
            {'YEAR': 2015, 'ACCOUNT': '1', 'AMT': 1500, 'NAME': 'John Doe'},
            {'YEAR': 2016, 'ACCOUNT': '1', 'AMT': 200, 'NAME': 'John Doe'},
            {'YEAR': 2017, 'ACCOUNT': '2', 'AMT': 1000, 'NAME': 'Jane Doe'}]
        ).sort_index(axis=1)

        self.assertTrue(returned.equals(expected))

    def test_get_donations_by_donor(self):
        """Test get_donations_by_donor()."""
        df = pd.DataFrame.from_dict([
            {'YEAR': 2015, 'ACCOUNT': '1', 'AMT': 500, 'NAME': 'John Doe'},
            {'YEAR': 2015, 'ACCOUNT': '1', 'AMT': 1000, 'NAME': 'John Doe'},
            {'YEAR': 2016, 'ACCOUNT': '1', 'AMT': 200, 'NAME': 'John Doe'},
            {'YEAR': 2017, 'ACCOUNT': '2', 'AMT': 500, 'NAME': 'Jane Doe'},
            {'YEAR': 2017, 'ACCOUNT': '2', 'AMT': 500, 'NAME': 'Jane Doe'}])

        returned = main.get_donations_by_donor(df).sort_index(axis=1)
        expected = pd.DataFrame.from_dict([
            {'YEAR': 'all-time', 'ACCOUNT': '1',
             'AMT': 1700, 'NAME': 'John Doe'},
            {'YEAR': 'all-time', 'ACCOUNT': '2',
             'AMT': 1000, 'NAME': 'Jane Doe'}]).sort_index(axis=1)

        self.assertTrue(returned.equals(expected))

    def test_get_slack_connection(self):
        """Test get_slack_connection() and credentials."""
        session = requests.Session()

        slack = main.get_slack_connection(session=session)
        assert slack.auth.test()

        session.close()

    def test_get_salesforce_connection(self):
        """Test get_salesforce_connection() and credentials."""
        session = requests.Session()

        sf = main.get_salesforce_connection(session=session)
        assert sf

        session.close()

    @patch('scripts.main.write_levels_csv')
    @patch('scripts.main.bin_donors_by_giving_level')
    def test_process_annual_donations(self, mock_bin, mock_csv):
        """Test process_annual_donations()."""
        df = pd.DataFrame.from_dict([{'YEAR': 2015},
                                     {'YEAR': 2016},
                                     {'YEAR': 2017}])

        mock_bin.return_value = df

        main.process_annual_donations(df)

        mock_csv_calls = [
            call(df[df['YEAR'] == 2015], '2015'),
            call(df[df['YEAR'] == 2016], '2016'),
            call(df[df['YEAR'] == 2017], '2017')]

        # Need to use Pandas' `.equals()` to test for equality instead of same.
        for i, mock_csv_call in enumerate(mock_csv_calls):
            self.assertTrue(mock_csv.call_args_list[i].equals(mock_csv_call))

if __name__ == '__main__':
    unittest.main()
