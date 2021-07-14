# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Before App Launch Hook

This hook is executed prior to application launch and is useful if you need
to set environment variables or run scripts as part of the app initialization.
"""

import os
import sys
import tank

# --- get Shotgun Desktop Console logging going...
import sgtk
logger = sgtk.platform.get_logger(__name__)
my_sep = ('=' * 10)

class BeforeAppLaunch(tank.Hook):
    """
    Hook to set up the system prior to app launch.
    """

    def execute(self, app_path, app_args, version, engine_name, **kwargs):
        """
        The execute functon of the hook will be called prior to starting the required application

        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in the
            "versions" settings of the Launcher instance, otherwise None
        :param engine_name (str) The name of the engine associated with the
            software about to be launched.

        """

        # accessing the current context (current shot, etc)
        # can be done via the parent object
        #
        # > multi_launchapp = self.parent
        # > current_entity = multi_launchapp.context.entity

        # you can set environment variables like this:
        # os.environ["MY_SETTING"] = "foo bar"

        # Log args
        logger.debug('engine_name >> '.format(engine_name))
        logger.debug('version >> '.format(version))

        os.environ["XBMLANGPATH"] = "X:\\tools\\release\\icons"

        # --- SG supplied ENVIRONMENT VARIABLES...
        os.environ['SG_APP_VERSION'] = '{}'.format(version)

        multi_launchapp = self.parent
        os.environ['SG_CURR_ENTITY'] = '{}'.format(multi_launchapp.context.entity)
        os.environ['SG_CURR_STEP'] = '{}'.format(multi_launchapp.context.step)
        os.environ['SG_CURR_TASK'] = '{}'.format(multi_launchapp.context.task)
        os.environ['SG_CURR_PROJECT'] = '{}'.format(multi_launchapp.context.project)
        os.environ['SG_CURR_LOCATIONS'] = '{}'.format(multi_launchapp.context.filesystem_locations)

        # --- get the correct studio tools in the paths (SYS & PYTHONPATH)...
        os.environ['CURR_PROJECT'] = '{}'.format(multi_launchapp.context.project['name'])

        project_name = os.environ['CURR_PROJECT']

        # --- Unified studio tools pathing!
        repo_path = self._return_repo_path(project_name)

        maya_script_paths = []
        maya_script_paths.append('{}/maya/scripts/mel'.format(repo_path))
        os.environ['MAYA_SCRIPT_PATH'] = ';'.join(maya_script_paths)
        maya_module_path = os.environ["MAYA_MODULE_PATH"]

        sg_a3_path = '{}/shotgun/api3'.format(repo_path)
        maya_tool_path = '{}/maya/scripts'.format(repo_path)
        module_path = '{}/maya/modules'.format(repo_path).replace('/', '\\') # --- idk: windows slashes req for maya modules?
        #nuke_plugin_path = '{}/nuke'.format(repo_path).replace('/', '\\')    # --- idk: windows slashes req for nuke paths?
        plugin_path = '{}/maya/plug-ins'.format(repo_path)

        script_paths = []
        script_paths.append(sg_a3_path)
        script_paths.append(maya_tool_path)
        for script_path in script_paths:
            sys.path.insert(0, script_path)

        for script_path in script_paths:
            old_py_path = os.environ['PYTHONPATH']
            if script_path in old_py_path:
                logger.debug('Found {} in PYTHONPATH, no need to add it.'.format(script_path))
            else:
                logger.debug('old_py_path: {}'.format(old_py_path))
                old_py_path_bits = old_py_path.split(';')

                old_py_path_bits.insert(0, script_path)
                new_py_path = ';'.join(old_py_path_bits)

                logger.debug('new_py_path: {}'.format(new_py_path))
                os.environ['PYTHONPATH'] = new_py_path

        # --- specific related to Maya versions...
        if version == "Maya2016":
            os.environ["MAYA_PLUG_IN_PATH"] = "X:\\tools\\maya\\plugins\\2016"

            golaem_home = "X:\\tools\\golaem\\v5.x"
            os.environ["MAYA_MODULE_PATH"] = golaem_home

            yeti_home = "X:\\tools\\yeti\\v2.x"
            os.environ["MAYA_PLUG_IN_PATH"] = os.environ["MAYA_PLUG_IN_PATH"] + os.pathsep + yeti_home + "\\plug-ins"
            os.environ["MAYA_SCRIPT_PATH"] = os.environ["MAYA_SCRIPT_PATH"] + os.pathsep + yeti_home + "\\scripts"

        elif version == "Maya2018":
            module_path = module_path + os.sep + '2018'
            logger.debug('module_path >> {}'.format(module_path))
            os.environ['MAYA_PLUG_IN_PATH'] = plugin_path + os.sep + '2018'

            os.environ["MAYA_PLUG_IN_PATH"] = os.environ["MAYA_PLUG_IN_PATH"] + os.pathsep + yeti_home + "\\plug-ins"
            os.environ["MAYA_SCRIPT_PATH"] = os.environ["MAYA_SCRIPT_PATH"] + os.pathsep + yeti_home + "\\scripts"

            module_list = [module_path]
            maya_module_path = (os.pathsep).join(module_list)
            logger.debug('maya_module_path >> {}'.format(maya_module_path))

            os.environ["MAYA_MODULE_PATH"] = maya_module_path

        else:
            print "No product/version specific environment variables required."

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

        # if you are using a shared hook to cover multiple applications,
        # you can use the engine setting to figure out which application
        # is currently being launched:
        #
        # > multi_launchapp = self.parent
        # > if multi_launchapp.get_setting("engine") == "tk-nuke":
        #       do_something()

    def env_paths_sanity_check(self):
        '''
        Print the lists of source paths to the Shotgun
        Desktop Console.
        '''
        env_var_str = []

        path_list = ['SYSTEM PATH',
                    'PYTHONPATH',
                    'MAYA_MODULE_PATH',
                    'MAYA_PLUG_IN_PATH',
                    'MAYA_SCRIPT_PATH'
                    ]

        for path_item in path_list:
            env_var_str.append(my_sep)
            env_var_str.append(path_item)
            env_var_str.append(my_sep)

            if path_item == 'SYSTEM PATH':
                logger.debug('path_item: {}'.format(path_item)
                for item in sys.path:
                    env_var_str.append(item)
            else:
                for item in os.environ[path_item].split(';'):
                    env_var_str.append(item)

        env_var_str.append(my_sep)

        for env_var_item in env_var_str:
            logger.debug(env_var_item)

    def _return_repo_path(self, project_name):
        """
        Use Shotgun (Toolkit and Database) to get data
        and return the correct code repo root path for
        the Project that Toolkit launched.
        @return str repo_path: The root of the path
                               based on information
                               gleaned from Shotgun.
        """
        repo_path = None

        logger.debug(my_sep)

        shotgun_inst = sgtk.api.shotgun.connection.get_sg_connection()
        sg_filters = [['project.Project.name', 'is', project_name]]
        sg_fields = ['id', 'code', 'project', 'sg_ss_tools_repo', 'windows_path']
        sgtk_configs = shotgun_inst.find('PipelineConfiguration', sg_filters, sg_fields)

        wanted_repo_key = None

        sg_auth = sgtk.get_authenticated_user()
        sgtk_core_user = sg_auth.login

        sgtk_module_path = sgtk.get_sgtk_module_path()
        if '\\' in sgtk_module_path:
            sgtk_module_path = sgtk_module_path.replace('\\', '/')
        sgtk_cfg_path = '/'.join(sgtk_module_path.split('/')[:5])
        logger.debug('sgtk_module_path >> {}'.format(sgtk_module_path))
        logger.debug('sgtk_cfg_path >> {}'.format(sgtk_cfg_path))

        for my_config in sgtk_configs:
            my_config_repo_key = my_config['sg_ss_tools_repo']
            my_config_path = my_config['windows_path']
            if '\\' in my_config_path:
                my_config_path = my_config_path.replace('\\', '/')
                if my_config_path == sgtk_cfg_path:
                    wanted_repo_key = my_config_repo_key
                    logger.debug('wanted_repo_key >> {}'.format(wanted_repo_key))
                    break

        if wanted_repo_key:
            if wanted_repo_key == 'dev':
                repo_path = 'X:/dev/ss_dev_{0}/{1}_repo'.format(sgtk_core_user, project_name)
                # --- If it's not a Project-specific repo, we have to resort to
                # --- the generic studio repo...
                if not os.path.exists(repo_path):
                    repo_path = 'X:/dev/ss_dev_{0}/ss_studio_repo'.format(sgtk_core_user, project_name)
            elif wanted_repo_key == 'project':
                repo_path = 'X:/tools/projects/{0}/{0}_repo'.format(project_name)
            else:
                repo_path = 'X:/tools/ss_studio_repo'
        logger.debug(my_sep)

        return repo_path
