import os
from lib.logger import TestLogger

class HtmlReport(object):

    def __init__(self, title, results, output_file):
        self.title = title
        self.results = results
        self.output_file = output_file
        self.logger = TestLogger(__name__)

    def generate(self):
        '''
        Generates the report
        '''
        report_content = self._get_header()
        report_content += "<body>\n"
        report_content += "<h1>" + self.title + "</h1>"
        report_content += "<table>\n"
        report_content += self._get_table_header()
        for result in self.results:
            report_content += "<tr>\n"
            #
            # 1st column: template name
            #
            report_content += "<td>" + result['name'] + "</td>\n"
            #
            # 2nd column: deployment status
            #
            status = None
            if result['deploy_error'] is None:
                status = 'SUCCESS'
                report_content += "<td bgcolor=\"#00FF00\">" + status + "</td>\n"
            else:
                status = 'FAILED'
                report_content += "<td bgcolor=\"#FF0000\">" + status + "</td>\n"
            #
            # 3rd column: deployment duration
            #
            duration = ""
            if 'deploy_duration' in result:
                #duration = "%.1f [s]" % result['deploy_duration']
                duration = "%s" % result['deploy_duration']
            report_content += "<td>" + duration + "</td>\n"
            #
            # 4th column: destroy status
            #
            status = ""
            if 'destroy_error' in result:
                if result['destroy_error'] is None:
                    status = 'SUCCESS'
                    report_content += "<td bgcolor=\"#00FF00\">" + status + "</td>\n"
                else:
                    status = 'FAILED'
                    report_content += "<td bgcolor=\"#FF0000\">" + status + "</td>\n"
            else: # destroy was skipped
                report_content += "<td bgcolor=\"#FF0000\">" + status + "</td>\n"
            #
            # 5th column: destroy duration
            #
            duration = ""
            if 'destroy_duration' in result:
                #duration = "%.1f [s]" % result['destroy_duration']
                duration = "%s" % result['destroy_duration']
            report_content += "<td>" + duration + "</td>\n"
            report_content += "</tr>\n"
        report_content += "\n</table>\n</body>"

        with open(self.output_file, 'w') as out:
            out.write(report_content)

        self.logger.info("Report %s generated." % os.path.abspath(self.output_file))

    def _get_header(self):
        header_file = os.path.join(os.path.dirname(__file__), 'report/header.html')
        with open(header_file, 'r') as header:
            return header.read()

    def _get_table_header(self):
        table_file = os.path.join(os.path.dirname(__file__), 'report/table.html')
        with open(table_file, 'r') as header:
            return header.read()
