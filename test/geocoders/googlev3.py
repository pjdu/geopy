import base64
import unittest
import warnings
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pytz import timezone

from geopy import exc
from geopy.geocoders import GoogleV3
from geopy.point import Point
from test.geocoders.util import GeocoderTestBase, env


@unittest.skipUnless(
    bool(env['GOOGLE_KEY']),
    "No GOOGLE_KEY env variable set"
)
class GoogleV3TestCase(GeocoderTestBase):
    new_york_point = Point(40.75376406311989, -73.98489005863667)
    america_new_york = timezone("America/New_York")

    @classmethod
    def setUpClass(cls):
        cls.geocoder = GoogleV3(api_key=env.get('GOOGLE_KEY'))

    def reverse_timezone_run(self, payload, expected):
        timezone = self._make_request(self.geocoder.reverse_timezone, **payload)
        if expected is None:
            self.assertIsNone(timezone)
        else:
            self.assertEqual(timezone.pytz_timezone, expected)

        return timezone

    def test_user_agent_custom(self):
        geocoder = GoogleV3(
            api_key='mock',
            user_agent='my_user_agent/1.0'
        )
        self.assertEqual(geocoder.headers['User-Agent'], 'my_user_agent/1.0')

    def test_configuration_error(self):
        """
        GoogleV3 raises configuration errors on invalid auth params
        """
        with self.assertRaises(exc.ConfigurationError):
            GoogleV3(api_key='mock', client_id='a')
        with self.assertRaises(exc.ConfigurationError):
            GoogleV3(api_key='mock', secret_key='a')

    def test_warning_with_no_api_key(self):
        """
        GoogleV3 warns if no API key is present
        """
        with warnings.catch_warnings(record=True) as w:
            GoogleV3()
        self.assertEqual(len(w), 1)

    def test_no_warning_with_no_api_key_but_using_premier(self):
        """
        GoogleV3 does not warn about the API key if using premier
        """
        with warnings.catch_warnings(record=True) as w:
            GoogleV3(client_id='client_id', secret_key='secret_key')
        self.assertEqual(len(w), 0)

    def test_check_status(self):
        """
        GoogleV3 raises correctly on Google-specific API status flags
        """
        self.assertEqual(self.geocoder._check_status("ZERO_RESULTS"), None)
        with self.assertRaises(exc.GeocoderQuotaExceeded):
            self.geocoder._check_status("OVER_QUERY_LIMIT")
        with self.assertRaises(exc.GeocoderQueryError):
            self.geocoder._check_status("REQUEST_DENIED")
        with self.assertRaises(exc.GeocoderQueryError):
            self.geocoder._check_status("INVALID_REQUEST")
        with self.assertRaises(exc.GeocoderQueryError):
            self.geocoder._check_status("_")

    def test_get_signed_url(self):
        """
        GoogleV3._get_signed_url
        """
        geocoder = GoogleV3(
            api_key='mock',
            client_id='my_client_id',
            secret_key=base64.urlsafe_b64encode('my_secret_key'.encode('utf8'))
        )
        self.assertTrue(geocoder.premier)
        # the two possible URLs handle both possible orders of the request
        # params; because it's unordered, either is possible, and each has
        # its own hash
        self.assertTrue(
            geocoder._get_signed_url(
                {'address': '1 5th Ave New York, NY'}
            ) in (
                "https://maps.googleapis.com/maps/api/geocode/json?"
                "address=1+5th+Ave+New+York%2C+NY&client=my_client_id&"
                "signature=Z_1zMBa3Xu0W4VmQfaBR8OQMnDM=",
                "https://maps.googleapis.com/maps/api/geocode/json?"
                "client=my_client_id&address=1+5th+Ave+New+York%2C+NY&"
                "signature=D3PL0cZJrJYfveGSNoGqrrMsz0M="
            )
        )

    def test_get_signed_url_with_channel(self):
        """
        GoogleV3._get_signed_url
        """
        geocoder = GoogleV3(
            api_key='mock',
            client_id='my_client_id',
            secret_key=base64.urlsafe_b64encode('my_secret_key'.encode('utf8')),
            channel='my_channel'
        )

        signed_url = geocoder._get_signed_url({'address': '1 5th Ave New York, NY'})
        params = parse_qs(urlparse(signed_url).query)

        self.assertTrue('channel' in params)
        self.assertTrue('signature' in params)
        self.assertTrue('client' in params)

    def test_format_components_param(self):
        """
        GoogleV3._format_components_param
        """
        f = GoogleV3._format_components_param
        self.assertEqual(f({}), '')
        self.assertEqual(f({'country': 'FR'}), 'country:FR')
        output = f({'administrative_area': 'CA', 'country': 'FR'})
        # the order the dict is iterated over is not important
        self.assertTrue(
            output in (
                'administrative_area:CA|country:FR',
                'country:FR|administrative_area:CA'
            ), output
        )

        with self.assertRaises(AttributeError):
            f(None)

        with self.assertRaises(AttributeError):
            f([])

        with self.assertRaises(AttributeError):
            f('administrative_area:CA|country:FR')

    def test_geocode(self):
        """
        GoogleV3.geocode
        """
        self.geocode_run(
            {"query": "435 north michigan ave, chicago il 60611 usa"},
            {"latitude": 41.890, "longitude": -87.624},
        )

    def test_unicode_name(self):
        """
        GoogleV3.geocode unicode
        """
        self.geocode_run(
            {"query": "\u6545\u5bab"},
            {"latitude": 39.916, "longitude": 116.390},
        )

    def test_geocode_with_conflicting_components(self):
        """
        GoogleV3.geocode returns None on conflicting components
        """
        self.geocode_run(
            {
                "query": "santa cruz",
                "components": {
                    "administrative_area": "CA",
                    "country": "FR"
                }
            },
            {},
            expect_failure=True
        )

    def test_components(self):
        """
        GoogleV3.geocode with components
        """
        self.geocode_run(
            {
                "query": "santa cruz",
                "components": {
                    "country": "ES"
                }
            },
            {"latitude": 28.4636296, "longitude": -16.2518467},
        )

    def test_components_without_query(self):
        self.geocode_run(
            {
                "components": {"city": "Paris", "country": "FR"},
            },
            {"latitude": 46.227638, "longitude": 2.213749},
        )

    def test_reverse(self):
        self.reverse_run(
            {"query": self.new_york_point},
            {"latitude": 40.75376406311989, "longitude": -73.98489005863667},
        )

    def test_zero_results(self):
        """
        GoogleV3.geocode returns None for no result
        """
        with self.assertRaises(exc.GeocoderQueryError):
            self.geocode_run(
                {"query": ''},
                {},
                expect_failure=True,
            )

    def test_timezone_datetime(self):
        self.reverse_timezone_run(
            {"query": self.new_york_point,
             "at_time": datetime.utcfromtimestamp(0)},
            self.america_new_york,
        )

    def test_timezone_at_time_normalization(self):
        utc_naive_dt = datetime(2010, 1, 1, 0, 0, 0)
        utc_timestamp = 1262304000
        self.assertEqual(
            utc_timestamp, self.geocoder._normalize_timezone_at_time(utc_naive_dt)
        )

        self.assertLess(
            utc_timestamp, self.geocoder._normalize_timezone_at_time(None)
        )

        tz = timezone("Etc/GMT-2")
        local_aware_dt = tz.localize(datetime(2010, 1, 1, 2, 0, 0))
        self.assertEqual(
            utc_timestamp, self.geocoder._normalize_timezone_at_time(local_aware_dt)
        )

    def test_timezone_integer_raises(self):
        # In geopy 1.x `at_time` could be an integer -- a unix timestamp.
        # This is an error since geopy 2.0.
        with self.assertRaises(exc.GeocoderQueryError):
            self.reverse_timezone_run(
                {"query": self.new_york_point, "at_time": 0},
                self.america_new_york,
            )

    def test_timezone_no_date(self):
        self.reverse_timezone_run(
            {"query": self.new_york_point},
            self.america_new_york,
        )

    def test_timezone_invalid_at_time(self):
        with self.assertRaises(exc.GeocoderQueryError):
            self.geocoder.reverse_timezone(self.new_york_point, at_time="eek")

    def test_reverse_timezone_unknown(self):
        self.reverse_timezone_run(
            # Google doesn't return a timezone for Antarctica.
            {"query": "89.0, 1.0"},
            None,
        )

    def test_geocode_bounds(self):
        """
        GoogleV3.geocode check bounds restriction
        """
        self.geocode_run(
            {"query": "221b Baker St", "bounds": [[50, -2], [55, 2]]},
            {"latitude": 51.52, "longitude": -0.15},
        )

    def test_geocode_bounds_invalid(self):
        """
        GoogleV3.geocode bounds must be 4-length iterable
        """
        with self.assertRaises(exc.GeocoderQueryError):
            self.geocode_run(
                {"query": "221b Baker St", "bounds": [50, -2, 55]},
                {"latitude": 51.52, "longitude": -0.15},
            )
