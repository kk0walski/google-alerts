#!/usr/bin/env python
"""Perform administrative actions on Google Alerts."""
import base64
import contextlib
import json
import os
import pickle
import sys
import time
from argparse import ArgumentParser
import selenium.webdriver as webdriver
from selenium_stealth import stealth
from google_alerts import GoogleAlerts

PY2 = False
if sys.version_info[0] < 3:
    PY2 = True

__author__ = "Brandon Dixon"
__copyright__ = "Copyright, Brandon Dixon"
__credits__ = ["Brandon Dixon"]
__license__ = "MIT"
__maintainer__ = "Brandon Dixon"
__email__ = "brandon@9bplus.com"
__status__ = "BETA"


AUTH_COOKIE_NAME = 'SIDCC'
CONFIG_PATH = os.path.expanduser('~/.config/google_alerts')
CONFIG_FILE = os.path.join(CONFIG_PATH, 'config.json')
SESSION_FILE = os.path.join(CONFIG_PATH, 'session')
CONFIG_DEFAULTS = {'email': '', 'password': '', 'py2': PY2}


def obfuscate(p, action):
    """Obfuscate the auth details to avoid easy snatching.

    It's best to use a throw away account for these alerts to avoid having
    your authentication put at risk by storing it locally.
    """
    key = "ru7sll3uQrGtDPcIW3okutpFLo6YYtd5bWSpbZJIopYQ0Du0a1WlhvJOaZEH"
    s = list()
    if action == 'store':
        if PY2:
            for i in range(len(p)):
                kc = key[i % len(key)]
                ec = chr((ord(p[i]) + ord(kc)) % 256)
                s.append(ec)
            return base64.urlsafe_b64encode("".join(s))
        else:
            return base64.urlsafe_b64encode(p.encode()).decode()
    else:
        if PY2:
            e = base64.urlsafe_b64decode(p)
            for i in range(len(e)):
                kc = key[i % len(key)]
                dc = chr((256 + ord(e[i]) - ord(kc)) % 256)
                s.append(dc)
            return "".join(s)
        else:
            e = base64.urlsafe_b64decode(p)
            return e.decode()


def main():
    """Run the core."""
    parser = ArgumentParser()
    subs = parser.add_subparsers(dest='cmd')
    setup_parser = subs.add_parser('setup')
    setup_parser.add_argument('-e', '--email', dest='email', required=True,
                              help='Email of the Google user.', type=str)
    setup_parser.add_argument('-p', '--password', dest='pwd', required=True,
                              help='Password of the Google user.', type=str)
    setup_parser = subs.add_parser('seed')
    setup_parser.add_argument('-d', '--driver', dest='driver',
                              required=True, type=str,
                              help='Location of the Chrome driver. This can be downloaded by visiting http://chromedriver.chromium.org/downloads',)
    setup_parser.add_argument('-t', '--timeout', dest='timeout',
                              required=False, type=int, default=20)
    setup_parser = subs.add_parser('list')
    setup_parser = subs.add_parser('create')
    setup_parser.add_argument('-t', '--term', dest='term', required=True,
                              help='Term to store.', type=str)
    setup_parser.add_argument('--exact', dest='exact', action='store_true',
                              help='Exact matches only for term.')
    setup_parser.add_argument('-d', '--delivery', dest='delivery',
                              required=True, choices=['rss', 'mail'],
                              help='Delivery method of results.')
    setup_parser.add_argument('-f', '--frequency', dest='frequency',
                              default="realtime", choices=['realtime', 'daily', 'weekly'],
                              help='Frequency to send results. RSS only allows for realtime alerting.')
    setup_parser = subs.add_parser('delete')
    setup_parser.add_argument('--id', dest='term_id', required=True,
                              help='ID of the term to find for deletion.',
                              type=str)
    args = parser.parse_args()

    if args.cmd == 'setup':
        if not os.path.exists(CONFIG_PATH):
            os.makedirs(CONFIG_PATH)
        if not os.path.exists(CONFIG_FILE):
            json.dump(CONFIG_DEFAULTS, open(CONFIG_FILE, 'w'), indent=4,
                      separators=(',', ': '))
        config = CONFIG_DEFAULTS
        config['email'] = args.email
        config['password'] = str(obfuscate(args.pwd, 'store'))
        json.dump(config, open(CONFIG_FILE, 'w'), indent=4,
                  separators=(',', ': '))

    config = json.load(open(CONFIG_FILE))
    if config.get('py2', PY2) != PY2:
        raise Exception("Python versions have changed. Please run `setup` again to reconfigure the client.")
    if config['password'] == '':
        raise Exception("Run setup before any other actions!")

    if args.cmd == 'seed':
        config['password'] = obfuscate(str(config['password']), 'fetch')
        ga = GoogleAlerts(config['email'], config['password'])
        options = webdriver.ChromeOptions()
        options.add_argument("start-maximized")
        # options.add_argument("--headless")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        with contextlib.closing(webdriver.Chrome(args.driver, options=options)) as driver:
            stealth(driver,
                user_agent='DN',
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )       # Before Login, using stealth
            driver.get('https://stackoverflow.com/users/signup?ssrc=head&returnurl=%2fusers%2fstory%2fcurrent%27')
            time.sleep(3)
            driver.find_element_by_xpath('//*[@id="openid-buttons"]/button[1]').click()
            driver.find_element_by_xpath('//input[@type="email"]').send_keys(config['email'])
            time.sleep(15)
            driver.find_element_by_xpath('//*[@id="identifierNext"]').click()
            time.sleep(3)
            driver.find_element_by_xpath('//input[@type="password"]').send_keys(config['password'])
            driver.find_element_by_xpath('//*[@id="passwordNext"]').click()
            time.sleep(3)
            driver.get('https://www.google.com/alerts')
            print("[*] Filled in password and submitted.")
            print("[!] Waiting for the authentication cookie or %d seconds" % args.timeout)
            for _ in range(0, args.timeout):
                cookies = driver.get_cookies()
                if [x for x in cookies if x['name'] == AUTH_COOKIE_NAME]:
                    break
                time.sleep(1)
            collected = dict()
            for cookie in cookies:
                collected[str(cookie['name'])] = str(cookie['value'])
            with open(SESSION_FILE, 'wb') as f:
                pickle.dump(collected, f, protocol=2)
        print("[$] Session has been seeded, google-alerts is ready for use.")

    if args.cmd == 'list':
        config['password'] = obfuscate(str(config['password']), 'fetch')
        ga = GoogleAlerts(config['email'], config['password'])
        ga.authenticate()
        print(json.dumps(ga.list(), indent=4))

    if args.cmd == 'create':
        config['password'] = obfuscate(str(config['password']), 'fetch')
        ga = GoogleAlerts(config['email'], config['password'])
        ga.authenticate()

        # 'realtime' is default, force it
        alert_frequency = 'as_it_happens'

        if args.frequency == 'daily':
            alert_frequency = 'at_most_once_a_day'
        if args.frequency == 'weekly':
            alert_frequency = 'at_most_once_a_week'

        monitor = ga.create(args.term, {'delivery': args.delivery.upper(),
                                        'alert_frequency': alert_frequency.upper(),
                                        'exact': args.exact})
        print(json.dumps(monitor, indent=4))

    if args.cmd == 'delete':
        config['password'] = obfuscate(str(config['password']), 'fetch')
        ga = GoogleAlerts(config['email'], config['password'])
        ga.authenticate()
        result = ga.delete(args.term_id)
        if result:
            print("%s was deleted" % args.term_id)


if __name__ == '__main__':
    main()
