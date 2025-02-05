import sys
import ntpath
import logging
import inspect
import traceback
from tauk.enums import TestStatusType
from tauk.utils import TestResult, format_appium_log, format_error
import requests
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException


class Tauk:

    logging.basicConfig(
        filename='.tauk-appium-sdk.log',
        level=logging.WARNING,
        filemode='w',
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    @classmethod
    def initialize(cls, **kwargs):
        """Initializes the Tauk SDK
        :param api_token: Your API Token from the Tauk Web Application
        :param project_id: Your Project ID from the Tauk Web Application
        :param driver: The Appium driver object
        """

        required_args = ['api_token', 'project_id']

        for arg in required_args:
            if arg not in kwargs:
                raise TypeError(f'Argument {arg} is required')

        cls._api_token = kwargs.get('api_token')
        cls._project_id = kwargs.get('project_id')
        cls._driver = kwargs.get('driver')
        cls._excluded = True if kwargs.get('excluded') else False
        cls._test_results = []

    @classmethod
    def _get_page_source(cls):
        if cls._driver:
            try:
                raw_page_source = cls._driver.page_source
            except:
                logging.error(
                    "An issue occurred while requesting the page source.")
                logging.error(traceback.format_exc())
                return None
            return raw_page_source
        else:
            return None

    @classmethod
    def _get_screenshot(cls):
        if cls._driver:
            try:
                screenshot = cls._driver.get_screenshot_as_base64()
            except:
                logging.error(
                    "An issue occurred while trying to take a screenshot.")
                logging.error(traceback.format_exc())
                return None
            return screenshot
        else:
            return None

    @classmethod
    def _get_log(cls):
        # Get last 100 log entries
        # minus the 5 log entries for issuing get_log()
        slice_range = slice(-105, -5)

        if cls._driver:
            try:
                log = cls._driver.get_log('server')[slice_range]
            except:
                logging.error(
                    "An issue occurred while requesting the Appium server logs.")
                logging.error(traceback.format_exc())
            return log
        else:
            return None

    @classmethod
    def _get_desired_capabilities(cls):
        if cls._driver:
            try:
                dc = cls._driver.desired_capabilities['desired']
            except:
                logging.error(
                    "An issue occurred while trying to retrieve the desired capabilities.")
                logging.error(traceback.format_exc())
            return dc
        else:
            return None

    @classmethod
    def observe(cls, func):

        caller_frame = inspect.stack()[1]
        caller_filename = ntpath.basename(caller_frame.filename)

        def invoke_test_case(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback_info = traceback.extract_tb(exc_traceback)
                filename, line_number, invoked_func, code_executed = traceback_info[-1]

                test_result = TestResult(
                    test_status=TestStatusType.excluded.name if cls._excluded else TestStatusType.failed.name,
                    test_name=func.__name__,
                    filename=caller_filename,
                    desired_caps=cls._get_desired_capabilities(),
                    appium_log=cls._get_log(),
                    page_source=cls._get_page_source(),
                    error=format_error(
                        error_type=str(exc_value.__class__.__name__),
                        error_msg=str(exc_value),
                        line_number=str(line_number),
                        invoked_func=str(invoked_func),
                        code_executed=str(code_executed)
                    )
                )
                test_result.screenshot = cls._get_screenshot()
                cls._test_results.append(test_result)
                # traceback.print_exception(exc_type, exc_value, exc_traceback, limit=-1)
                # raise exc_type(exc_value).with_traceback(exc_traceback.tb_next)
                raise
            else:
                test_result = TestResult(
                    test_status=TestStatusType.excluded.name if cls._excluded else TestStatusType.passed.name,
                    test_name=func.__name__,
                    filename=caller_filename,
                    desired_caps=cls._get_desired_capabilities(),
                    appium_log=cls._get_log(),
                    page_source=cls._get_page_source(),
                    error=None
                )
                test_result.screenshot = cls._get_screenshot()
                cls._test_results.append(test_result)

                return result
        return invoke_test_case

    @classmethod
    def upload(cls, custom_session_upload_url=None):
        headers = {
            'api-token': cls._api_token,
            'project-id': cls._project_id
        }

        if len(cls._test_results) > 0:
            for test_result in cls._test_results:
                payload = {
                    'test-status': test_result.status,
                    'test-name': test_result.name,
                    'test-filename': test_result.filename,
                    'tags': test_result.desired_caps,
                    'log': format_appium_log(test_result.log),
                    'screenshot': test_result.screenshot,
                    'view': test_result.page_source,
                    'errors': test_result.error,
                    'automation-type': 'appium',
                    'sdk-language': 'python'
                }

                try:
                    response = requests.request(
                        "POST",
                        custom_session_upload_url if custom_session_upload_url else 'https://www.tauk.com/api/v1/session/upload',
                        headers=headers,
                        json=payload,
                        timeout=(15, 15)
                    )
                    response.raise_for_status()

                except HTTPError as http_status_error:
                    logging.error("An HTTP status code error occurred.")
                    logging.error(http_status_error)
                    logging.error(response.text)
                except ConnectionError as connection_error:
                    logging.error("An error connecting to the API occurred.")
                    logging.error(connection_error)
                    logging.error(response.text)
                except Timeout as timeout_error:
                    logging.error("A timeout error occurred.")
                    logging.error(timeout_error)
                    logging.error(response.text)
                except RequestException as request_error:
                    logging.error(
                        "An error occurred trying to make an upload request.")
                    logging.error(request_error)
                    logging.error(response.text)
