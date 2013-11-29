#!/usr/bin/python
import os
import sys
import subprocess
import shutil
import datetime
from xml.dom import minidom


class br():
    def __init__(self):
        # the program which performs build (make) 
        self._make=['c:/Windows/Microsoft.NET/Framework64/v4.0.30319/msbuild.exe'];
        # the parameters for this program
        self._make_par=['/nologo','/m:12','/nr:false']
        # the parameters for making configuration
        self._cmake   = ['cmake']
        # cmake parameters:
        self._cmake_par = ['-G','Visual Studio 11 Win64','-DCONSOLE=ON','-DMAKE_VATES=ON','-DENABLE_CPACK=ON','-DQT_ASSISTANT_FETCH_IMAGES=OFF','-DUSE_PRECOMPILED_HEADERS=ON','-DParaView_DIR=d:/programming/ParaView-3.98.1-source/win64']

        # default mantid git repository location:
        self._MANTID_Loc='c:/Mantid/'
        #self._MANTID_Loc='d:/Data/Mantid_GIT_dev/'
        #self._MANTID_Loc='d:/Data/Mantid_GIT/'

        # build location with respect to the Mantid Git repository location
        self._MANT_Build_relLoc='Code/builds/'
        # mantid path template specifying all additional references to libraries to build Mantid
        self._MANTID_Path_base='c:/programming/Paraview_3_28Dev/bin;{MANTID}Code/Third_Party/lib/win64;{MANTID}/Code/Third_Party/lib/win64/Python27;{PATH}'
        # set PATH=C:\Builds\ParaView-3.98.1-source\build\bin\Release;%WORKSPACE%\Code\Third_Party\lib\win64;%WORKSPACE%\Code\Third_Party\lib\win64\Python27;%PATH%
        # mantid projects necessary for short build (minimal projects to start Mantid):
        self._MANTID_short=['Framework','MantidPlot','MantidQT/Python']

        # cmd: the command processor for the enviroment to build the project and the batch files to set up necessary enviroment
        self._cmd = 'cmd.exe /s /c "{0} && echo "{1}" && set"'
        # the bat file used to set up enviroment or nothing if the enviroment to build has been set up globally on the current machine
        self._set_up_env = 'c:/programming/VS2012/VC/vcvarsall.bat';

        # default file name for the log file
        path = os.getcwd();
        self._log_fname = os.path.join(path,'br_job_log_file.log');
  
    @property
    def log_fname(self):
        return self._log_fname
    @log_fname.setter
    def log_fname(self,new_fname):

        if os.path.isabs(new_fname):
            self._log_fname = new_fname;
        else:
            path = os.getcwd();
            self._log_fname = os.path.join(path,new_fname);

    def run_build(self,target,buildType=None,env=None):
        """
        method runs build for the project and if the short build fails, tries to rebuild the project/
        runs nmake
        Assumes that the branch to build is current and cmake has already build the project directory and the project file 
    
        @param target     -- the name of the target project (sln file, build by cmake)
        @param build_type -- type of the project build, which the target project understands (Debug, Release, ReleaseWithDebugInfo). If None, uses Release
        @param env        -- the enviromental variables necessary to run msbuild/mvc -- if none, the OS has to be set up to find MSBuild & mvc from command line


        """

        if buildType is None:
            buildType  = 'Release'

        # form the build command combining make progam and its parameters
        normalBuild=self._make+self._make_par+['/p:Configuration='+buildType,target]

        # run build command
        err=subprocess.call(normalBuild,env=env)
        if err != 0:
            # form the rebuild command combining make progam and its parameters
            Rebuild = self._make+self._make_par+['/p:Configuration='+buildType,'/t:Rebuild',target]
            err=subprocess.call(Rebuild,env=env)

        return err

    def build_single_proj(self,args):
        """
        build single project from command line:

        >>br build [*Release|Debug|DebWithRel] [*Full|Fast] [*Old|Clean]

        assumes that the branch to build is checked out 
        """
        for arg in args:
            print " transferred argument: ",arg

        env =  self.get_environment_from_batch_command(self._set_up_env)
        branchID = self.find_cur_branch_id();
        if len(branchID)==0:
            repo_path =  self._MANTID_Loc;
            cur_path = os.getcwd()+'/';
            os.chdir(repo_path)           
            branchID = self.find_cur_branch_id();
            if len(branchID)==0:
                raise EnvironmentError("Can not swich to default GIT repository location")
            os.chdir(cur_path);
        else:
            repo_path = os.getcwd()+'/';

        # where to build the project
        build_path= self.find_target_build_path(branchID,repo_path,False);
        short = False;
        build_clean = False
        build_type = 'Release'
        self.build_project(env,repo_path,build_path,True,short,build_clean,build_type)


    def build_project(self,env,repo_path,build_path,first_build=True,short=False,build_clean=False,buildType=None):
        """
        Build current project using cmake and msbuild

        env   -- enviromental variables necessary to build the project
        build_path -- the folder to build the project 
        short -- if minimal rebuild, namely minimal number of projects to start Mantid gui is needed 
        build_clean -- delete the target project build directory if its already exist
        buildType   -- The type of the build, make understants (Debug, Release etc...)

        assumes that the brunch to build is current branch
        """


        # modify path to understand Mantid project and Mantid libraries. 
        loc_env = dict()
        loc_env['PATH'] = env['Path'];
        loc_env['MANTID']= repo_path;
        env['Path']=self._MANTID_Path_base.format(**loc_env);  


        current_dir  = os.getcwd();
        build_exists = os.path.exists(build_path);

        if build_clean and build_exists:
            shutil.rmtree(build_path,True)
            build_exists=os.path.exists(build_path)

        if not build_exists:
            os.mkdir(build_path);

        os.chdir(build_path )

        if first_build:
            # form cmake command:
            # code path:
            code_path  = repo_path+'Code/Mantid'
            cmake = self._cmake+self._cmake_par+[code_path]
            # run cmake
            err=subprocess.call(cmake,env=env)
            if err != 0:
                os.chdir(current_dir);
                raise RuntimeError("Can not execute cmake")

        # run msbuild
        if short :
            # process minimal set of projects, necessary to start and run Mantid
            for proj in self._MANTID_short:
                os.chdir(build_path+'/'+proj)
                err=self.run_build(proj+'.vcxproj',buildType,env);
                if err>0:
                    errMessage="Can not execute msbuild for :"+proj+'.vcxproj';
                    break
        else:
            errMessage="Can not execute msbuild for : Mantid.sln"
            err=self.run_build('Mantid.sln',buildType,env);
   

        # return back to the source directory
        os.chdir(current_dir);
        if err != 0:
            raise RuntimeError(errMessage)


    def get_environment_from_batch_command(self,env_cmd):
        """
        Take a command (either a single command or list of arguments)
        and return the environment created after running that command.
        Note that if the command must be a batch file or .cmd file, or the
        changes to the environment will not be captured.
  
        """
        if not isinstance(env_cmd, (list, tuple)):
            env_cmd = [env_cmd]
        # construct the command that will alter the environment
        env_cmd = subprocess.list2cmdline(env_cmd)
        # create a tag so we can tell in the output when the proc is done
        tag = 'Done running command'
        # construct a cmd.exe command to do accomplish this
        cmd = self._cmd.format(env_cmd,tag)

        # launch the process
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        # parse the output sent to stdout
        reject = True
        result={};
    # define a way to handle each KEY=VALUE line
        handle_line = lambda l: l.rstrip().split('=',1)
        for line in proc.stdout:
            # consume whatever output occurs until the tag is reached
            if not reject:
                kv = handle_line(line);
                result[kv[0]]=kv[1];
                continue
            if tag in line:           
                reject = False

        # let the process finish
        proc.communicate()
        return result
    def build_target_br_name(self,br_ID_to_merge_to,source_br_ID):
        """
        defines convention for target branch name and calculates this name from the source branches names;
        """
        rez = '__'+str(br_ID_to_merge_to);
        if br_ID_to_merge_to != source_br_ID:
           rez = rez+'_'+str(source_br_ID);

           return rez;

    def find_target_build_path(self,branch_id,merge_id,repo_root,build_on_base):
        """
        Build target build path from defaults or add branch ID to it
        """
        if not(repo_root[len(repo_root)-1] == '/' or repo_root[len(repo_root)-1] == '\\' ):
            repo_root +='/'
        if build_on_base :
            build_path = repo_root+self._MANT_Build_relLoc+'br_master';
        else:
            if merge_id == branch_id:
                build_path = repo_root+self._MANT_Build_relLoc+'br_'+str(branch_id);
            else:
                build_path = repo_root+self._MANT_Build_relLoc+'br_'+str(merge_id)+'_'+str(branch_id);

        return build_path;

    def find_cur_branch_id(self):
        """
        returns current branch ID (the string between / and number including number
        or empty string if not on a branch 
        """
        err = subprocess.call(['git','status'])
        if err != 0: # not on Git
            return ""

        # get the names of the current branch of the the repository
        result = subprocess.check_output(['git','rev-parse','--abbrev-ref','HEAD']) # 
        rez = result.split('/');
        if len(rez)>1:
            result = rez[-1];
        rez = result.split('_')
        if len(rez) == 1:
            return rez

        result = "";
        for parts in rez:
            try:
                int(parts)
                result = result+parts;
                break;
            except ValueError:
                result =result+part+'_';
        return result

    def find_full_banch_name(self,branch_id,exclude_service=True):
        """
        find full branch name on GIT from the branch id 
        branch id is a piece of string or number, which identifies the branch.
        (e.g. the ticket number)

        it assumes that the current folder is a git folder
        """

        # get the names of all branches in the repository
        result = subprocess.check_output(['git','branch','-a']) # 

        branch_id = str(branch_id)
        branches = result.split('\n')
        local_branch_name="";
        remote_branch_name="";
        for branch_name in branches:
            if '*' in branch_name:
                current_branch = branch_name.strip('* ')
                branch_name    = current_branch


            branch_name = branch_name.strip();

            # skip service branches which can be target only and never the source
            if branch_name[:2] == '__' and exclude_service:
                continue

            if branch_id in branch_name:
                if 'remote' in branch_name:
                    full_name = branch_name.split('origin/');
                    remote_branch_name = full_name[1]
                else:
                    local_branch_name = branch_name


        if len(local_branch_name) == 0 and len(remote_branch_name) == 0: 
            return "","ERR: can not find the branch with ID {0} ".format(branch_id),current_branch


        return local_branch_name,remote_branch_name,current_branch;

    @staticmethod
    def check_branch_synchronized(branch_name, other_branch_name = None):
        # check if local branch indeed synchronized with the remote branch
        if other_branch_name is None:
            other_branch_name = 'origin/'+branch_name
        try:
            result = subprocess.check_output(['git','diff',branch_name,other_branch_name]) # 
        except:
            return False

        if len(result) == 0:
            return True
        else:
            return False

    @staticmethod
    def check_and_remove_existing(hold_on_branch):
        """
        """
       # get the names of local branches in the repository
        err=""
        result = subprocess.check_output(['git','branch']) # 
        if hold_on_branch in result:
            err = subprocess.call(['git','branch','-D',hold_on_branch]) #
            if err!=0: # may be we are on this branch?
                err = subprocess.call(['git','checkout','master']) #
                err = subprocess.call(['git','branch','-D',hold_on_branch]) #
        return err

    @staticmethod
    def convert_boolean(attribute,field_name):
        """
          get boolean attribute from field name and convert its symbolic contents to boolean
        """
        field_contents=attribute.getAttribute(field_name)
        if len(field_contents) == 0 or field_contents != 'True':
                field_contents =False
        else:
                field_contents =True

        return field_contents

        
    def get_job_attributes(self,job):
        """
        processes xml string to obtain job attributes from it
        """
        # The ID of the branch (ticket number )
        branch_ID = job.getAttribute("branch_ID");

        # 
        repo_root  = job.getAttribute("mantid_root")
        if len(repo_root) == 0:
                repo_root = self._MANTID_Loc
        if not(repo_root[len(repo_root)-1] == '/' or repo_root[len(repo_root)-1] == '\\' ):
            repo_root +='/'


        merge_to = job.getAttribute("merge_to")
        if len(merge_to) == 0:
                merge_to = branch_ID

        build_on_base = self.convert_boolean(job,"build_on_base")
        skip_this     = self.convert_boolean(job,"skip_this")
        clean_build   = self.convert_boolean(job,"clean_build")


        return branch_ID,repo_root,merge_to,build_on_base,skip_this,clean_build

    def prepare_working_branch(self,archive_path,merge_to_ID,branch_id,dry_run=False):
        """
        method checks if the branch identified by ID is present, 
        merges it with specified branch ID and 
        returns the GIT name of branch to build.
        The name is constructed from the branch id(s) if the branch do not exist. 

        returns tupe (err,branch_name) if everything is ok err is empty string
        """

        current_dir=os.getcwd();
        os.chdir(archive_path);

        # update repository info
        err = subprocess.call(['git','fetch','-p'])
        if err != 0 :
           return "ERR: can not fetch current repository status";


        wk_local_branch,wk_remote_branch,current_branch = self.find_full_banch_name(branch_id);
        if 'ERR:' in wk_local_branch:
            return "TargetBranch: {0} in archive: {1}".format(wk_remote_branch,archive_path),"";
        # we want to build current branch which does not have remote. just stay with current local branch
        if wk_local_branch == current_branch and len(wk_remote_branch)==0:
            return "",current_branch

        # only one branch has been given and it is the branch we need to build
        if branch_id == merge_to_ID:
            merge_remote_branch = wk_remote_branch
            merge_local_branch  = wk_local_branch
            err = subprocess.call(['git','checkout',merge_local_branch])
            if err != 0 :
                  return "ERR: checkout target branch: "+merge_local_branch,"";

            err = subprocess.call(['git','pull'])
            if err != 0 :
                  return "ERR: pull target branch: "+merge_local_branch,"";

            return "",merge_local_branch;
        else:
            merge_local_branch,merge_remote_branch,current_branch = self.find_full_banch_name(merge_to_ID);
            if 'ERR:' in merge_remote_branch :
                return "Base branch: {0} in archive: {1}".format(merge_remote_branch,archive_path),"";
                
        #-------------------------------------------------------------------------------------------

        # the branch which will be created from two source branches (e.g for testing). 
        # It sould not be real branch present on Git or branch which contan any reasonable 
        # information on it
        holdon_br_name = self.build_target_br_name(merge_to_ID,branch_id);
        if holdon_br_name == current_branch: # merge both branches into it
            err = self.merge_2current(wk_local_branch,wk_remote_branch);
            if len(err)==0:
                  err = self.merge_2current(merge_local_branch,merge_remote_branch);
        else:                              # create this branch, delete it if it existed
            holdon_local_branch,holdon_remote_branch,current_branch = self.find_full_banch_name(holdon_br_name,False);
            if len(holdon_local_branch) == 0 : # no such branch, has to be created
                err=self.merge_one2another_and_create_new(wk_local_branch,wk_remote_branch,merge_local_branch,merge_remote_branch,holdon_br_name);
            else :                             # branch found, 
              if len(holdon_remote_branch)>0: # has remote counterpart;
                return "Remote Hold-on branch {0} in archive {1} exists. Do not know what to do about it".format(holdon_br_name,archive_path),"";
              else: # local hold-on branch exist and it is not the current branch
                    # delete existing local hold-on branch according to the git workflow
                    err = subprocess.call(['git','branch','-D',holdon_local_branch])
                    if err != 0 :
                            return "ERR: deleting base branch: {0}".format(holdon_local_branch),"";
    
                    err=self.merge_one2another_and_create_new(wk_local_branch,wk_remote_branch,merge_local_branch,merge_remote_branch,holdon_br_name);

        os.chdir(current_dir);
        return err,holdon_br_name

    @staticmethod  
    def merge_2current(br1_local,br1_remote):
        """
        """
        if len(br1_local)>0:
            err= subprocess.call(['git','merge',br1_local])
            if err != 0 :
                err= subprocess.call(['git','merge','--abort'])
                return "ERR: merging "+br1_local+" to current branch"
            else:
                err ="";
        else:
           if len(br1_remote)>0:
                err= subprocess.call(['git','merge','origin/'+br1_remote])
                if err != 0 :
                    err= subprocess.call(['git','merge','--abort'])
                    return "ERR: merging "+br1_remote+" to current branch"
                else:
                    err="";
           else:
                err="ERR: both local and remote branches are empty"
        #
        if br1_local != br1_remote :
                err= subprocess.call(['git','merge','origin/'+br1_remote])
                if err != 0 :
                    err= subprocess.call(['git','merge','--abort'])
                    return "ERR: merging "+br1_remote+" to current branch"
                else:
                    err="";


        return err;

    def merge_one2another_and_create_new(self,wk_local_branch,wk_remote_branch,merge_local_branch,merge_remote_branch,holdon_br_name):
        """
        """
        if len(wk_local_branch) > 0 and len(wk_remote_branch)>0: # local branch exist
            err = subprocess.call(['git','checkout',wk_local_branch])
            if err != 0 :
               return "ERR: checkout working branch: "+wk_local_branch;
            err = subprocess.call(['git','pull',wk_local_branch])
            if err != 0 :
               return "ERR: pulling working branch: "+wk_local_branch;
        #else:  # local working branch does not exist, will work with remote


        err = subprocess.call(['git','checkout',merge_local_branch])
        if err != 0 :
            return "ERR: checkout merge branch: "+merge_local_branch;
        if len(merge_remote_branch)>0:
            err = subprocess.call(['git','pull'])
            if err != 0 :
               return "ERR: pulling merge branch: "+merge_remote_branch;

        # create new branch from the merge branch to work with
        err = subprocess.call(['git','checkout','-b', holdon_br_name])
        if err != 0 :
            return "ERR: creating new branch  "+holdon_br_name; 

        # merge with target local branch
        err = self.merge_2current(wk_local_branch,wk_remote_branch);
        if len(err)>0:
            return err+' to '+merge_local_branch;

        return "";


    def run_batch_job(self,*argi):
        """
        runs batch job described by the job description file provided as argument

        Usage: br batch [job_description_file]

        job_description_file is xml file with the information understood by cron_job. It can be full file path or file name 
        for file availible in the search path

        if no job description file provided, default job file is used.       
        """
        default_job_descr = 'job_description.xml'
        batch_par = argi[0];
        if len(batch_par) < 1:
            job_descr = default_job_descr 
        else:
            job_descr= batch_par[0];

        if not os.path.exists(job_descr):
            raise RuntimeError("Can not find job description file: {0}".format(job_descr))

        #self.cron_job(job_descr,True); # Dry run
        self.cron_job(job_descr); 


    def append_log(self,string_to_add):
        """
        """
        #f=open(self.log_fname,'a')
        #f.write(string_to_add);
        #f.close();
        with open(self.log_fname,'a') as f:
            f.write(string_to_add);


    def cron_job(self,job_description_file,dry_run=False):
        """ method processes job description file and runs all mantid build job described there
        """

        # found job description file and prepare log file with the same name

        if os.path.isabs(job_description_file):
            path,file = os.path.split(job_description_file);
        else:
            path = os.getcwd();
            file = job_description_file;

        fname,fext = os.path.splitext(file);
        self._log_fname = os.path.join(path,fname + '.log');

        log_head=datetime.datetime.now().strftime(":%B,%d,%Y::%I:%M%p::")
        mess = ("----------------------------------------------------------------------\n"
                "{0} Starting cron jobs for parameters: {1}\n").format(log_head,job_description_file)
        self.append_log(mess);


        # parce job description file
        try:
            domObj=minidom.parse(job_description_file)
        except Exception as error:
            err_type = type(error)
            mess = "{0} ERR: problem with job description file: {1} in working folder {2} \n err type: {3}\n".format(log_head,job_description_file,os.getcwd(),err_type);
            self.append_log(mess);
            return
        jobs = domObj.getElementsByTagName("job")

        env = {}
        if len(jobs) == 0:
            log_head='+'.ljust(len(log_head))
            self.append_log("{0}, No jobs found".format(log_head))
            return
        else:
            env =  self.get_environment_from_batch_command(self._set_up_env)

        # go through all jobs in job description and run them with the parameters, obtained from the job description
        for job in jobs :
            # retrieve job attribute or its default values if the attributes are missing
            branch_ID,repo_root,merge_to,build_on_base,skip_this,clean_build =self.get_job_attributes(job)
            if skip_this:
                 log_head=datetime.datetime.now().strftime(":%B,%d,%Y::%I:%M%p::")
                 self.append_log("{0} Skipping job with ID {1} \n".format(log_head,branch_ID))
                 continue


            Target_path = self.find_target_build_path(branch_ID,merge_to,repo_root,build_on_base)

            # prepare branches to build e.g pull/create/merge it from GIT and change code to it. Return its name for logging purposes
            err,local_branch_toBuild = self.prepare_working_branch(repo_root,merge_to,branch_ID);
            if len(err) != 0:
                    log_head='+'.ljust(len(log_head))
                    self.append_log("{0}, Can not prepare source branch: {1}, scipping this job\n".format(log_head,err))
                    continue


            # Go through all kind of builds selected for the branch
            builds = job.getElementsByTagName('build')
            # set first build to True to allow cmake to run
            fast_build = False
            first_build  = True
            key_log = "Skipping"
            if dry_run :
                key_log = "Dry Run "
            for buildType in builds:
                build_type  = buildType.getAttribute('type')
                fast_build  = self.convert_boolean(buildType,"minmal_build")
                skip_this   = self.convert_boolean(buildType,"skip_this")
                log_head=datetime.datetime.now().strftime(":%B,%d,%Y::%I:%M%p::")
                if skip_this or dry_run:
                    self.append_log("{0} {4} build {3} run for Mantid, branch {1} located in: {2} \n".format(log_head,local_branch_toBuild,repo_root,build_type,key_log))
                    continue

                self.append_log("{0} Starting {3} run for Mantid, branch {1} located in: {2} \n".format(log_head,local_branch_toBuild,repo_root,build_type))

                # Try to build actual project
                try:
                     self.build_project(env,repo_root,Target_path,first_build,fast_build,clean_build,build_type)
                     # second build do not need cmake to run
                     first_build  = False
                     log_head=datetime.datetime.now().strftime(":%B,%d,%Y::%I:%M%p::")
                     self.append_log("{0} Finished {2} run for Mantid, branch {1} \n".format(log_head,branch_ID,build_type))
                except RuntimeError, err:
                     #log_head=datetime.datetime.now().strftime(":%B,%d,%Y::%I:%M%p::")
                     log_head='+'.ljust(len(log_head))
                     self.append_log("{0} ERR: {1} while builging target project {2}\n".format(log_head,str(err),build_type))
                     

                # second buid type should not be clean as it will wipe out the first build regardless of the first run was successfull or not
                clean_build = False


        log_head=datetime.datetime.now().strftime(":%B,%d,%Y::%I:%M%p::")
        self.append_log(("{0} finished Mantid cron job {1}\n"+
                         "--------------------------------\n").format(log_head,job_description_file))     
    def help(self,**kwargs):
        """
        """
        if len(kwargs) == 0:
            print "Usage: >>br de[bug]|re[lease]||cr[on]|[dwr|DebWithRelInfo] parameters "
            print "Where paramerers are the option specific values namely: "
            print ""
            print "br debug|release|DebWithRelInfo [fast]  -- build debug/release/debug with release version of the build"
            print "Where ""fast"" if present means minumal rebuild. The build occurs for the branch and repository you are currently in."
            print "If working directory is not the Git repository, br changes to default git repository, defined in the script"
if __name__ == '__main__':
    builder = br();
    nargi = len(sys.argv);
    if nargi <2:
        builder.help()
        exit

    option = sys.argv[1].lower();

    known_options={};
    known_options['proj']=lambda : builder.build_single_proj(sys.argv[2:nargi])
    known_options['batch']=lambda : builder.run_batch_job(sys.argv[2:nargi])

    if option in known_options:
         known_options[option]();
    else:
        print "br Unknown parameter: ",option
        builder.help()

    #builder.cron_job(job_name)
    
 #   run_key = args[1](0:2)
#    if 
# Testing
#    current_dir=os.getcwd();
#    os.chdir('C:/mantid');

#    bl,br,cb,bbp=builder.find_full_banch_name("4060")

##    is_sync=builder.check_branch_synchronized(bn);
#    os.chdir(current_dir);

    #builder.check_merges('job_description.xml')
    #tp = builder.prepare_working_parh_and_branch(builder._MANTID_Loc,'master',7492);

    #env = builder.get_environment_from_batch_command(builder._set_up_env)
    #builder.build_project(env,builder._MANT_Build_relLoc,True,True);

