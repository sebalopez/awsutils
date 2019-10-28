import jenkins

# Connects to a provided Jenkins server and triggers jobs
 
class JenkinsClient(object):
    
    # url must be complete endpoint, eg http://jenkins.privatedomain.co:8080
    def __init__(self, url, user=None, pwd=None):
        self.url = url
        if user == None:
            self.server = jenkins.Jenkins(url)
        else:
            self.server = jenkins.Jenkins(url, username=user, password=pwd)

    # params must be a dictionary in the format:
    # {'param1': 'test value 1', 'param2': 'test value 2'}
    def run_job(self, jobname, params=None):
        if params == None:
            self.server.build_job(jobname)
        else:
            self.server.build_job(jobname, params)
        build = self.server.get_job_info(jobname)['nextBuildNumber']
        print 'Build for job %s started.' %jobname
        print 'Build URL: %s/job/%s/%s/' %(self.url,jobname,build)
        return build