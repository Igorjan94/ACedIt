import sys
import json
import re
import os
try:
    from bs4 import BeautifulSoup as bs
    import grequests as grq
    import requests as rq
    from argparse import ArgumentParser
except:
    err = """
    You haven't installed the required dependencies.
    Run 'python setup.py install' to install the dependencies.
    """
    print(err)
    sys.exit(0)


class Utilities:

    cache_dir = os.path.join(os.path.expanduser('~'), '.cache', 'ACedIt')
    colors = {
        'GREEN': '\033[92m',
        'YELLOW': '\033[93m',
        'RED': '\033[91m',
        'ENDC': '\033[0m',
        'BOLD': '\033[1m',
    }
    verdicts = {
        'AC': colors['BOLD'] + colors['GREEN'] + 'AC' + colors['ENDC'],
        'WA': colors['BOLD'] + colors['RED'] + 'WA' + colors['ENDC'],
        'RTE': colors['BOLD'] + colors['RED'] + 'RTE' + colors['ENDC'],
        'TLE': colors['BOLD'] + colors['YELLOW'] + 'TLE' + colors['ENDC']
    }

    @staticmethod
    def parse_flags(supported_sites):
        """
        Utility function to parse command line flags
        """

        parser = ArgumentParser()

        parser.add_argument('-s', '--site',
                            dest='site',
                            choices=supported_sites,
                            help='The competitive programming platform, e.g. codeforces, codechef etc')

        parser.add_argument('-c', '--contest',
                            dest='contest',
                            help='The name of the contest, e.g. JUNE17, LTIME49, COOK83 etc')

        parser.add_argument('-p', '--problem',
                            dest='problem',
                            help='The problem code, e.g. OAK, PRMQ etc')

        parser.add_argument('-f', '--force',
                            dest='force',
                            action='store_true',
                            help='Force download the test cases, even if they are cached')

        parser.add_argument('--add-test',
                            dest='add_test',
                            action='store_true',
                            help='Add test to specific problem of contest')

        parser.add_argument('--run',
                            dest='source_file',
                            help='Name of source file to be run')

        parser.add_argument('--set-default-site',
                            dest='default_site',
                            choices=supported_sites,
                            help='Name of default site to be used when -s flag is not specified')

        parser.add_argument('--set-default-contest',
                            dest='default_contest',
                            help='Name of default contest to be used when -c flag is not specified')

        parser.add_argument('--clear-cache',
                            dest='clear_cache',
                            action='store_true',
                            help='Clear cached test cases for a given site. Takes default site if -s flag is omitted')

        parser.set_defaults(force=False, clear_cache=False)

        args = parser.parse_args()

        flags = {}

        if args.site is None or args.contest is None:
            import json
            site, contest = None, None
            try:
                with open(os.path.join(Utilities.cache_dir, 'constants.json'), 'r') as f:
                    data = f.read()
                data = json.loads(data)
                site = data.get(
                    'default_site', None) if args.site is None else args.site
                contest = data.get(
                    'default_contest', None) if args.contest is None else args.contest
            except:
                pass

            flags['site'] = site
            flags['contest'] = contest if not site == 'spoj' else None
        else:
            flags['site'] = args.site
            flags['contest'] = args.contest

        flags['problem'] = args.problem
        flags['force'] = args.force
        flags['clear_cache'] = args.clear_cache
        flags['source'] = args.source_file
        flags['default_site'] = args.default_site
        flags['default_contest'] = args.default_contest
        flags['add_test'] = args.add_test

        return flags

    @staticmethod
    def set_constants(key, value):
        """
        Utility method to set default site and contest
        """
        with open(os.path.join(Utilities.cache_dir, 'constants.json'), 'r+') as f:
            data = f.read()
            data = json.loads(data)
            data[key] = value
            f.seek(0)
            f.write(json.dumps(data, indent=2))
            f.truncate()

        print('Set %s to %s' % (key, value))

    @staticmethod
    def check_cache(site, contest, problem):
        """
        Method to check if the test cases already exist in cache
        If not, create the directory structure to store test cases
        """

        if problem is None:
            if not os.path.isdir(os.path.join(Utilities.cache_dir, site, contest)):
                os.makedirs(os.path.join(Utilities.cache_dir, site,
                                         contest))
            return False

        # Handle case for SPOJ specially as it does not have contests
        contest = '' if site == 'spoj' else contest

        if os.path.isdir(os.path.join(Utilities.cache_dir, site, contest, problem)):
            return True
        else:
            os.makedirs(os.path.join(Utilities.cache_dir, site,
                                     contest, problem))
            return False

    @staticmethod
    def clear_cache(site):
        """
        Method to clear cached test cases
        """

        confirm = raw_input(
            'Remove entire cache for site %s? (y/N) : ' % (site))
        if confirm == 'y':
            from shutil import rmtree
            try:
                rmtree(os.path.join(Utilities.cache_dir, site))
            except:
                print('Some error occured. Try again.')
                return
            os.makedirs(os.path.join(Utilities.cache_dir, site))
            print('Done.')

    @staticmethod
    def get_long_input(message):
        print(message)
        lines = []
        while True:
            try:
                line = raw_input()
                if line == '' and len(lines) > 0 and lines[-1] == '':
                    break
            except EOFError:
                lines.append('')
                break
            lines.append(line)
        return '\n'.join(lines)

    @staticmethod
    def add_test(args):
        print('Adding new test to %s (contest: %s, problem: %s)' % (args['site'], args['contest'], args['problem']))
        inputs = [Utilities.get_long_input('Specify input (^D or two consecutive empty lines to stop):')]
        outputs = [Utilities.get_long_input('Specify output (^D or two consecutive empty lines to stop):')]
        is_in_cache = Utilities.check_cache(args['site'], args['contest'], args['problem'])
        Utilities.store_files(args['site'], args['contest'], args['problem'], inputs, outputs)
        print('Test is successfully added')

    @staticmethod
    def getTestCasesCount(p):
        return len([f for f in os.listdir(p) if f.endswith('.a')])

    @staticmethod
    def store_files(site, contest, problem, inputs, outputs, statement=None):
        """
        Method to store the test cases in files
        """

        # Handle case for SPOJ specially as it does not have contests
        contest = '' if site == 'spoj' else contest
        testcases_path = os.path.join(Utilities.cache_dir, site, contest, problem)
        num_cases = Utilities.getTestCasesCount(testcases_path)
        def writeFile(filename, content):
            with open(filename, 'w') as handler:
                handler.write(content)

        for i, inp in enumerate(inputs):
            writeFile(os.path.join(testcases_path, str(i + num_cases)), inp)

        for i, out in enumerate(outputs):
            writeFile(os.path.join(testcases_path, str(i + num_cases) + '.a'), out)

        if statement:
            writeFile(os.path.join(testcases_path, 'statement.txt'), statement)

    @staticmethod
    def get_platform(args):
        if args['site'] == 'codeforces':
            return Codeforces(args)
        elif args['site'] == 'codechef':
            return Codechef(args)
        elif args['site'] == 'spoj':
            return Spoj(args)
        else:
            return Hackerrank(args)

    @staticmethod
    def download_problem_testcases(args):
        """
        Download test cases for a given problem
        """
        platform = Utilities.get_platform(args)
        is_in_cache = Utilities.check_cache(
            platform.site, platform.contest, platform.problem)

        if not args['force'] and is_in_cache:
            print('Test cases found in cache...')
            sys.exit(0)

        platform.scrape_problem()

    @staticmethod
    def download_contest_testcases(args):
        """
        Download test cases for all problems in a given contest
        """
        platform = Utilities.get_platform(args)
        Utilities.check_cache(
            platform.site, platform.contest, platform.problem)

        platform.scrape_contest()

    @staticmethod
    def input_file_to_string(path, num_cases):
        """
        Method to return sample inputs as a list
        """
        inputs = []

        for i in xrange(num_cases):
            with open(os.path.join(path, str(i)), 'r') as fh:
                inputs += [fh.read()]

        return inputs

    @staticmethod
    def cleanup(num_cases, basename, extension):
        """
        Method to clean up temporarily created files
        """
        for i in xrange(num_cases):
            if os.path.isfile('temp_output' + str(i)):
                os.remove('temp_output' + str(i))

        if extension == 'java':
            os.system('rm ' + basename + '*.class')

    @staticmethod
    def handle_kbd_interrupt(site, contest, problem):
        """
        Method to handle keyboard interrupt
        """
        from shutil import rmtree
        print('Cleaning up...')

        # Handle case for SPOJ specially as it does not have contests
        contest = '' if site == 'spoj' else contest

        # if problem is not None:
            # path = os.path.join(Utilities.cache_dir, site, contest, problem)
            # if os.path.isdir(path):
                # rmtree(path)
        # else:
            # path = os.path.join(Utilities.cache_dir, site, contest)
            # if os.path.isdir(path):
                # rmtree(path)

        print('Done. Exiting gracefully.')

    @staticmethod
    def run_command_on_one_test(testcases_path, testcase_number, execute_command):
        status = os.system('timeout 2s ' + execute_command + ' < ' + os.path.join(
            testcases_path, str(testcase_number)) + ' > temp_output' + str(testcase_number))
        user_output = ''
        with open(os.path.join(testcases_path, str(testcase_number) + '.a'), 'r') as out_handler:
            expected_output = out_handler.read().strip().split('\n')
            expected_output = '\n'.join([line.strip() for line in expected_output])
            if status == 124:
                # Time Limit Exceeded
                results = Utilities.verdicts['TLE']

            elif status == 0:
                # Ran successfully
                with open('temp_output' + str(testcase_number), 'r') as temp_handler:
                    user_output = temp_handler.read().strip().split('\n')
                    user_output = '\n'.join([line.strip() for line in user_output])

                if expected_output == user_output:
                    # All Correct
                    results = Utilities.verdicts['AC']
                else:
                    # Wrong Answer
                    results = Utilities.verdicts['WA']

            else:
                # Runtime Error
                results = Utilities.verdicts['RTE']
        return (expected_output, user_output, results)

    @staticmethod
    def run_solution(args):
        """
        Method to run and test the user's solution against sample cases
        """
        problem = args['source']

        extension = problem.split('.')[-1]
        problem = problem.split('.')[0]
        basename = problem.split('/')[-1]
        problem_path = os.path.join(os.getcwd(), problem)

        if not os.path.isfile(problem_path + '.' + extension):
            print('ERROR : No such file')
            sys.exit(0)

        problem_code = args['problem'] if args['problem'] else problem
        contest_code = '' if args['site'] == 'spoj' else args['contest']

        testcases_path = os.path.join(Utilities.cache_dir, args[
                                      'site'], contest_code, problem_code)

        if os.path.isdir(testcases_path):
            num_cases = Utilities.getTestCasesCount(testcases_path)
            results, expected_outputs, user_outputs = [''] * num_cases, [''] * num_cases, [''] * num_cases

            if extension in ['c', 'cpp', 'java', 'py', 'hs', 'rb', 'kt']:

                compiler = {
                    'hs': 'ghc --make -O -dynamic -o ' + basename,
                    'py': None,
                    'rb': None,
                    'c': 'gcc -static -DONLINE_JUDGE -fno-asm -lm -s -O2 -o ' + basename,
                    'cpp': 'clang++ -DONLINE_JUDGE -include /home/igorjan/206round/bits.h -O2 -std=c++17 -o ' + basename,
                    'java': 'javac -d .',
                    'kt': 'kotlinc -d .'
                }[extension]
                execute_command = {
                    'py': 'python ' + basename + '.' + extension,
                    'rb': 'ruby ' + basename + '.' + extension,
                    'hs': './' + basename,
                    'c': './' + basename,
                    'cpp': './' + basename,
                    'java': 'java -DONLINE_JUDGE=true -Duser.language=en -Duser.region=US -Duser.variant=US ' + basename,
                    'kt': 'kotlin -DONLINE_JUDGE=true -Duser.language=en -Duser.region=US -Duser.variant=US ' + basename + 'Kt'
                }[extension]
                if compiler is None:
                    compile_status = 0
                else:
                    compile_status = os.system(compiler + ' \'' + problem_path + '.' + extension + '\'')

                if compile_status == 0:

                    # Compiled successfully
                    for i in xrange(num_cases):
                        expected_outputs[i], user_outputs[i], results[i] = Utilities.run_command_on_one_test(testcases_path, i, execute_command)
                else:
                    # Compilation error occurred
                    message = Utilities.colors['BOLD'] + Utilities.colors[
                        'RED'] + 'Compilation error. Not run against test cases' + Utilities.colors['ENDC'] + '.'
                    prin((message))
                    sys.exit(0)

            else:
                print('Supports only C, C++, Python, Java and Kotlin as of now.')
                sys.exit(0)

            from terminaltables import AsciiTable
            table_data = [['Serial No', 'Input',
                           'Expected Output', 'Your Output', 'Result']]

            inputs = Utilities.input_file_to_string(testcases_path, num_cases)

            for i in xrange(num_cases):

                row = [
                    i + 1,
                    inputs[i],
                    expected_outputs[i],
                    user_outputs[i] if any(sub in results[i]
                                           for sub in ['AC', 'WA']) else 'N/A',
                    results[i]
                ]

                table_data.append(row)

            table = AsciiTable(table_data)

            print(table.table)

            # Clean up temporary files
            Utilities.cleanup(num_cases, basename, extension)

        else:
            print('Test cases not found locally...')

            args['problem'] = problem_code
            args['force'] = True
            args['source'] = problem + '.' + extension

            Utilities.download_problem_testcases(args)

            print('Running your solution against sample cases...')
            Utilities.run_solution(args)

    @staticmethod
    def get_html(url):
        """
        Utility function get the html content of an url
        """
        MAX_TRIES = 3
        try:
            for try_count in range(MAX_TRIES):
                r = rq.get(url)
                if r.status_code == 200:
                    break
            if try_count >= MAX_TRIES:
                print('Could not fetch content. Please try again.')
                sys.exit(0)
        except Exception as e:
            print('Please check your internet connection and try again.')
            sys.exit(0)
        return r


class Codeforces:
    """
    Class to handle downloading of test cases from Codeforces
    """

    def __init__(self, args):
        self.site = args['site']
        self.contest = args['contest']
        self.problem = args['problem']
        self.force_download = args['force']
        self.url = 'https://codeforces.com'
        self.locale = 'locale=ru'

    def parse_html(self, req):
        """
        Method to parse the html and get test cases
        from a codeforces problem
        """
        soup = bs(req.text, 'html.parser')

        inputs = soup.findAll('div', {'class': 'input'})
        outputs = soup.findAll('div', {'class': 'output'})
        statements = soup.findAll('div', {'class': 'problem-statement'})

        if len(inputs) == 0 or len(outputs) == 0:
            print('Problem not found...')
            Utilities.handle_kbd_interrupt(
                self.site, self.contest, self.problem)
            sys.exit(0)

        tags = ('<br>', '\n'), ('<br/>', '\n'), ('</br>', ''), ('</p>', '\n'), ('<p>', '\n'), ('<div>', '\n'), ('</div>', '\n'), ('<li>', '\n *')
        htmls = [('$$$', ''),
            ('\\le', '<='),
            ('\\ge', '>='),
            ('\\neq', '!='),
            ('&gt;', '>'),
            ('&lt;', '<'),
            ('\\ldots', '...'),
            ('\\dots', '...'),
            ('\\ ', ' '),
            ('\\cdot', '*'),
            ('\\rightarrow', '->'),
            ('\\leftarrow', '<-')]

        def getContent(inp, tag=None):
            if not tag: inp = inp.find('pre')
            s = inp.decode_contents()
            s = reduce(lambda a, kv: a.replace(*kv), tags, s)
            s = re.sub('<[^<]+?>', '', s)
            s = reduce(lambda a, kv: a.replace(*kv), htmls, s)
            s = re.sub('\n{2,}', '\n\n', s)
            return re.sub(r'^\s*', '', s)

        formatted_inputs = list(map(getContent, inputs))
        formatted_outputs = list(map(getContent, outputs))
        formatted_text = [getContent(statements[0], True)]

        # print('Inputs', ''.join(formatted_inputs))
        # print('Outputs', ''.join(formatted_outputs))
        # print('Statements', ''.join(formatted_text))

        return formatted_inputs, formatted_outputs, ''.join(formatted_text)

    def get_problem_links(self, req):
        """
        Method to get the links for the problems
        in a given codeforces contest
        """
        soup = bs(req.text, 'html.parser')

        table = soup.find('table', {'class': 'problems'})

        if table is None:
            print('Contest not found...')
            Utilities.handle_kbd_interrupt(
                self.site, self.contest, self.problem)
            sys.exit(0)

        links = ['%s%s?%s' % (self.url, td.find('a')['href'], self.locale) for td in table.findAll('td', {'class': 'id'})]

        return links

    def handle_batch_requests(self, links):
        """
        Method to send simultaneous requests to
        all problem pages
        """
        rs = (grq.get(link) for link in links)
        responses = grq.map(rs)

        failed_requests = []

        for response in responses:
            if response is not None and response.status_code == 200:
                inputs, outputs, text = self.parse_html(response)
                self.problem = response.url.split('/')[-1].split('?')[0]
                Utilities.check_cache(self.site, self.contest, self.problem)
                Utilities.store_files(self.site, self.contest, self.problem, inputs, outputs, text)
            else:
                failed_requests += [response.url]

        return failed_requests

    def scrape_problem(self):
        """
        Method to scrape a single problem from codeforces
        """
        print('Fetching problem ' + self.contest + '-' + self.problem + ' from Codeforces...')
        type = 'contest' if int(self.contest) <= 100000 else 'gym'
        url = '%s/%s/%s/problem/%s?%s' % (self.url, type, self.contest, self.problem, self.locale)
        req = Utilities.get_html(url)
        inputs, outputs, text = self.parse_html(req)
        Utilities.store_files(self.site, self.contest, self.problem, inputs, outputs, text)
        print('Done.')

    def scrape_contest(self):
        """
        Method to scrape all problems from a given codeforces contest
        """
        print('Checking problems available for contest ' + self.contest + '...')
        type = 'contest' if int(self.contest) <= 100000 else 'gym'
        url = '%s/%s/%s?%s' % (self.url, type, self.contest, self.locale)
        req = Utilities.get_html(url)
        links = self.get_problem_links(req)

        print('Found %d problems..' % (len(links)))

        if not self.force_download:
            cached_problems = os.listdir(os.path.join(
                Utilities.cache_dir, self.site, self.contest))
            links = [link for link in links if link.split(
                '/')[-1] not in cached_problems]

        failed_requests = self.handle_batch_requests(links)
        if len(failed_requests) > 0:
            self.handle_batch_requests(failed_requests)


class Codechef:
    """
    Class to handle downloading of test cases from Codechef
    """

    def __init__(self, args):
        self.site = args['site']
        self.contest = args['contest']
        self.problem = args['problem']
        self.force_download = args['force']

    def parse_html(self, req):
        """
        Method to parse the html and get test cases
        from a codechef problem
        """
        try:
            data = json.loads(req.text)
            soup = bs(data['body'], 'html.parser')
        except (KeyError, ValueError):
            print('Problem not found..')
            Utilities.handle_kbd_interrupt(
                self.site, self.contest, self.problem)
            sys.exit(0)

        test_cases = soup.findAll('pre')
        formatted_inputs, formatted_outputs = [], []

        input_list = [
            '<pre>(.|\n)*<b>Input:?</b>:?',
            '<b>Output:?</b>(.|\n)+</pre>'
        ]

        output_list = [
            '<pre>(.|\n)+<b>Output:?</b>:?',
            '</pre>'
        ]

        input_regex = re.compile('(%s)' % '|'.join(input_list))
        output_regex = re.compile('(%s)' % '|'.join(output_list))

        for case in test_cases:
            inp = input_regex.sub('', str(case))
            out = output_regex.sub('', str(case))

            inp = re.sub('<[^<]+?>', '', inp)
            out = re.sub('<[^<]+?>', '', out)

            formatted_inputs += [inp.strip()]
            formatted_outputs += [out.strip()]

        # print('Inputs', formatted_inputs)
        # print('Outputs', formatted_outputs)

        return formatted_inputs, formatted_outputs

    def get_problem_links(self, req):
        """
        Method to get the links for the problems
        in a given codechef contest
        """
        soup = bs(req.text, 'html.parser')

        table = soup.find('table', {'class': 'dataTable'})

        if table is None:
            print('Contest not found...')
            Utilities.handle_kbd_interrupt(
                self.site, self.contest, self.problem)
            sys.exit(0)

        links = [div.find('a')['href']
                 for div in table.findAll('div', {'class': 'problemname'})]
        links = ['https://codechef.com/api/contests/' + self.contest +
                 '/problems/' + link.split('/')[-1] for link in links]

        return links

    def handle_batch_requests(self, links):
        """
        Method to send simultaneous requests to
        all problem pages
        """
        rs = (grq.get(link) for link in links)
        responses = grq.map(rs)

        # responses = []
        # for link in links:
        #     responses += [rq.get(link)]

        failed_requests = []

        for response in responses:
            if response is not None and response.status_code == 200:
                inputs, outputs = self.parse_html(response)
                self.problem = response.url.split('/')[-1]
                Utilities.check_cache(self.site, self.contest, self.problem)
                Utilities.store_files(
                    self.site, self.contest, self.problem, inputs, outputs)
            else:
                failed_requests += [response.url]

        return failed_requests

    def scrape_problem(self):
        """
        Method to scrape a single problem from codechef
        """
        print('Fetching problem ' + self.contest + '-' + self.problem + ' from Codechef...')
        url = 'https://codechef.com/api/contests/' + \
            self.contest + '/problems/' + self.problem
        req = Utilities.get_html(url)
        inputs, outputs = self.parse_html(req)
        Utilities.store_files(self.site, self.contest,
                              self.problem, inputs, outputs)
        print('Done.')

    def scrape_contest(self):
        """
        Method to scrape all problems from a given codechef contest
        """
        print('Checking problems available for contest ' + self.contest + '...')
        url = 'https://codechef.com/' + self.contest
        req = Utilities.get_html(url)
        links = self.get_problem_links(req)

        print('Found %d problems..' % (len(links)))

        if not self.force_download:
            cached_problems = os.listdir(os.path.join(
                Utilities.cache_dir, self.site, self.contest))
            links = [link for link in links if link.split(
                '/')[-1] not in cached_problems]

        failed_requests = self.handle_batch_requests(links)
        if len(failed_requests) > 0:
            self.handle_batch_requests(failed_requests)


class Spoj:
    """
    Class to handle downloading of test cases from Spoj
    """

    def __init__(self, args):
        self.site = args['site']
        self.contest = args['contest']
        self.problem = args['problem'].upper()
        self.force_download = args['force']

    def parse_html(self, req):
        """
        Method to parse the html and get test cases
        from a spoj problem
        """
        soup = bs(req.text, 'html.parser')

        test_cases = soup.findAll('pre')

        if test_cases is None or len(test_cases) == 0:
            print('Problem not found..')
            Utilities.handle_kbd_interrupt(
                self.site, self.contest, self.problem)
            sys.exit(0)

        formatted_inputs, formatted_outputs = [], []

        input_list = [
            '<pre>(.|\n|\r)*<b>Input:?</b>:?',
            '<b>Output:?</b>(.|\n|\r)*'
        ]

        output_list = [
            '<pre>(.|\n|\r)*<b>Output:?</b>:?',
            '</pre>'
        ]

        input_regex = re.compile('(%s)' % '|'.join(input_list))
        output_regex = re.compile('(%s)' % '|'.join(output_list))

        for case in test_cases:
            inp = input_regex.sub('', str(case))
            out = output_regex.sub('', str(case))

            inp = re.sub('<[^<]+?>', '', inp)
            out = re.sub('<[^<]+?>', '', out)

            formatted_inputs += [inp.strip()]
            formatted_outputs += [out.strip()]

        # print('Inputs', formatted_inputs)
        # print('Outputs', formatted_outputs)

        return formatted_inputs, formatted_outputs

    def scrape_problem(self):
        """
        Method to scrape a single problem from spoj
        """
        print('Fetching problem ' + self.problem + ' from SPOJ...')
        url = 'http://spoj.com/problems/' + self.problem
        req = Utilities.get_html(url)
        inputs, outputs = self.parse_html(req)
        Utilities.store_files(self.site, self.contest,
                              self.problem, inputs, outputs)
        print('Done.')


class Hackerrank:
    """
    Class to handle downloading of test cases from Hackerrank
    """

    def __init__(self, args):
        self.site = args['site']
        self.contest = args['contest']
        self.problem = '-'.join(args['problem'].split()
                                ).lower() if args['problem'] is not None else None
        self.force_download = args['force']

    def parse_html(self, req):
        """
        Method to parse the html and get test cases
        from a hackerrank problem
        """

        try:
            data = json.loads(req.text)
            soup = bs(data['model']['body_html'], 'html.parser')
        except (KeyError, ValueError):
            print('Problem not found..')
            Utilities.handle_kbd_interrupt(
                self.site, self.contest, self.problem)
            sys.exit(0)

        input_divs = soup.findAll('div', {'class': 'challenge_sample_input'})
        output_divs = soup.findAll('div', {'class': 'challenge_sample_output'})

        inputs = [input_div.find('pre') for input_div in input_divs]
        outputs = [output_div.find('pre') for output_div in output_divs]

        regex_list = [
            '<pre>(<code>)?',
            '(</code>)?</pre>'
        ]

        regex = re.compile('(%s)' % '|'.join(regex_list))

        formatted_inputs, formatted_outputs = [], []

        for inp in inputs:
            spans = inp.findAll('span')
            if len(spans) > 0:
                formatted_input = '\n'.join(
                    [span.decode_contents() for span in spans])
            else:
                formatted_input = regex.sub('', str(inp))

            formatted_inputs += [formatted_input.strip()]

        for out in outputs:
            spans = out.findAll('span')
            if len(spans) > 0:
                formatted_output = '\n'.join(
                    [span.decode_contents() for span in spans])
            else:
                formatted_output = regex.sub('', str(out))

            formatted_outputs += [formatted_output.strip()]

        # print('Inputs', formatted_inputs)
        # print('Outputs', formatted_outputs)

        return formatted_inputs, formatted_outputs

    def get_problem_links(self, req):
        """
        Method to get the links for the problems
        in a given hackerrank contest
        """

        try:
            data = json.loads(req.text)
            data = data['models']
        except (KeyError, ValueError):
            print('Contest not found..')
            Utilities.handle_kbd_interrupt(
                self.site, self.contest, self.problem)
            sys.exit(0)

        links = ['https://www.hackerrank.com/rest/contests/' + self.contest +
                 '/challenges/' + problem['slug'] for problem in data]

        return links

    def handle_batch_requests(self, links):
        """
        Method to send simultaneous requests to
        all problem pages
        """
        rs = (grq.get(link) for link in links)
        responses = grq.map(rs)

        failed_requests = []

        for response in responses:
            if response is not None and response.status_code == 200:
                inputs, outputs = self.parse_html(response)
                self.problem = response.url.split('/')[-1]
                Utilities.check_cache(self.site, self.contest, self.problem)
                Utilities.store_files(
                    self.site, self.contest, self.problem, inputs, outputs)
            else:
                failed_requests += [response.url]

        return failed_requests

    def scrape_problem(self):
        """
        Method to scrape a single problem from hackerrank
        """
        print('Fetching problem ' + self.contest + '-' + self.problem + ' from Hackerrank...')
        url = 'https://www.hackerrank.com/rest/contests/' + \
            self.contest + '/challenges/' + self.problem
        req = Utilities.get_html(url)
        inputs, outputs = self.parse_html(req)
        Utilities.store_files(self.site, self.contest,
                              self.problem, inputs, outputs)
        print('Done.')

    def scrape_contest(self):
        """
        Method to scrape all problems from a given hackerrank contest
        """
        print('Checking problems available for contest ' + self.contest + '...')
        url = 'https://www.hackerrank.com/rest/contests/' + self.contest + '/challenges'
        req = Utilities.get_html(url)
        links = self.get_problem_links(req)

        print('Found %d problems..' % (len(links)))

        if not self.force_download:
            cached_problems = os.listdir(os.path.join(
                Utilities.cache_dir, self.site, self.contest))
            links = [link for link in links if link.split(
                '/')[-1] not in cached_problems]

        failed_requests = self.handle_batch_requests(links)
        if len(failed_requests) > 0:
            self.handle_batch_requests(failed_requests)
