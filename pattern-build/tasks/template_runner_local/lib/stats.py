import os

def _total(data):
    total = None

    for i in data:
        if not total:
            total = i
        else:
            total += i
    return total

def dump(stats, target_file='./stats.txt', start_time=None, end_time=None):
    '''
    Generates a report based on the statistics
    '''

    dep_durations = []
    del_durations = []

    failed_deps = []
    failed_dels = []

    for i in stats:
        if i['deploy_error']:
            failed_deps.append(i['stack_name'])
        else:
            dep_durations.append(i['deploy_duration'])

        if 'destroy_error' in i:
            if i['destroy_error']:
                failed_dels.append(i['stack_name'])
            else:
                del_durations.append(i['destroy_duration'])
    
    average_dep = 'N/A'
    average_del = 'N/A'

    max_dep = 'N/A'
    max_del = 'N/A'

    min_dep = 'N/A'
    min_del = 'N/A'

    if len(del_durations) > 0:
        average_del = _total(del_durations) / len(del_durations)
        min_del = min(del_durations)
        max_del = max(del_durations)

    if len(dep_durations) > 0:
        average_dep = _total(dep_durations) / len(dep_durations)
        min_dep = min(dep_durations)
        max_dep = max(dep_durations)

    report_file = open(target_file, 'w')

    try:
        report_file.write('Region used: %s\n' % os.environ['BLUEMIX_REGION'])
        report_file.write('Org used: %s\n' % os.environ['BLUEMIX_ORG_NAME'])
        report_file.write('Space used: %s\n' % os.environ['BLUEMIX_SPACE_NAME'])
    except:
        pass

    try:
        report_file.write('VM used: %s\n' % os.environ['VM_URL'])
    except:
        pass

    try:
        report_file.write('AWS connection: %s\n' % os.environ['AWS_CLOUD_CONNECTION'])
    except:
        pass
    
    try:
        report_file.write('IBM Cloud connection: %s\n\n' % os.environ['IBMCLOUD_CLOUD_CONNECTION'])
    except:
        pass

    try:
        report_file.write('Number of workers: %s\n' % os.environ['NUMBER_WORKERS'])
    except:
        pass
    
    try:
        report_file.write('Test environment: %s\n' % os.environ['TEST_ENVIRONMENT'])
    except:
        pass
    
    try:
        report_file.write('Stress test report: %s\n' % os.environ['STRESS_REPORT'])
    except:
        pass
    
    try:
        report_file.write('Stat collection interval: %ss\n\n' % os.environ['STAT_COLLECTION_INTERVAL'])
    except:
        pass

    # Start/End times
    if start_time:
        report_file.write('Start time: %s\n' % start_time)

    if end_time:
        report_file.write('End time: %s\n' % end_time)

    # Deploy stats
    report_file.write('\nNumber of attempted deployments: %s\n' %
                      (len(dep_durations) + len(failed_deps)))
    report_file.write('Number of failed: %s\nNumber of passed: %s' %
                      (len(failed_deps), len(dep_durations)))
    report_file.write('\nAverage duration for success: %s' %
                      (average_dep))
    report_file.write('\nMinimum time: %s' % min_dep)
    report_file.write('\nMaximum time: %s' % max_dep)

    # Delete stats
    report_file.write('\n\nNumber of attempted deletes: %s\n' %
                      (len(del_durations) + len(failed_dels)))
    report_file.write('Number of failed: %s\nNumber of passed: %s' %
                      (len(failed_dels), len(del_durations)))
    report_file.write('\nAverage duration for success: %s' %
                      (average_del))
    report_file.write('\nMinimum time: %s' % min_del)
    report_file.write('\nMaximum time: %s' % max_del)

    if len(failed_deps) > 0:
        report_file.write('\n\nFailed deployments:\n')
        for i in failed_deps:
            report_file.write(i + '\n')

    if len(failed_dels) > 0:
        report_file.write('\n\nFailed deletions:\n')
        for i in failed_dels:
            report_file.write(i + '\n')

    report_file.close()
