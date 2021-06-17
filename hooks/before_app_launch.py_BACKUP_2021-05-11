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
LOGGER = sgtk.platform.get_logger(__name__)
MY_SEP = ('=' * 10)

# --- global variables...
OCIO_CONFIG = 'X:/tools/aces/aces_1.0.3/config.ocio'


class BeforeAppLaunch(tank.Hook):
    """
    Hook to set up the system prior to app launch.
    """

    def execute(self, app_path, app_args, version, engine_name, **kwargs):
        """
        The execute functon of the hook will be called prior to starting the
        required application

        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in
            the "versions" settings of the Launcher instance, otherwise None
        :param engine_name (str) The name of the engine associated with the
            software about to be launched.

        """
        # accessing the current context (current shot, etc)
        # can be done via the parent object
        #
        # > multi_launchapp = self.parent
        # > current_entity = multi_launchapp.context.entity
        #
        # you can set environment variables like this:
        # os.environ["MY_SETTING"] = "foo bar"

        # Log args
        LOGGER.debug('app_path    > {}'.format(app_path))
        LOGGER.debug('app_args    > {}'.format(app_args))
        LOGGER.debug('version     > {}'.format(version))
        LOGGER.debug('engine_name > {}'.format(engine_name))
        LOGGER.debug('kwargs      > {}'.format(kwargs))

        os.environ["XBMLANGPATH"] = "X:\\tools\\release\\icons"

        # --- SG supplied ENVIRONMENT VARIABLES...
        os.environ['SG_APP_VERSION'] = '{}'.format(version)

        multi_launchapp = self.parent
        ml_context = multi_launchapp.context
        os.environ['SG_CURR_ENTITY'] = '{}'.format(ml_context.entity)
        os.environ['SG_CURR_STEP'] = '{}'.format(ml_context.step)
        os.environ['SG_CURR_TASK'] = '{}'.format(ml_context.task)
        os.environ['SG_CURR_PROJECT'] = '{}'.format(ml_context.project)
        os.environ['SG_CURR_LOCATIONS'] = '{}'.format(
            ml_context.filesystem_locations
        )

        # --- get the correct studio tools in the paths (SYS & PYTHONPATH)...
        os.environ['CURR_PROJECT'] = '{}'.format(ml_context.project['name'])
        project_name = os.environ['CURR_PROJECT']

        # --- Set instance variables...
        self._version = version
        self._engine_name = engine_name

        # --- Unified studio tools pathing!
        self._repo_path = self._return_repo_path(project_name)

        # --- Make the SSE Shotgun API available...
        self._sg_a3_path = '{}/shotgun/api3'.format(self._repo_path)

        # --- Call methods based on the Toolkit engine we're invoking
        # --- (e.g. Maya > 'tk-maya', Nuke > 'tk-nuke', etc.)...
        if engine_name == 'tk-maya':
            self._tk_maya_env_setup()

        if engine_name == 'tk-nuke':
            self._tk_nuke_env_setup()

        if engine_name == 'tk-aftereffects':
            self._tk_aftereffects_env_setup()

        if engine_name == 'tk-houdini':
            self._tk_houdini_env_setup()

        if engine_name == 'tk-natron':
            self._tk_natron_env_setup()


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

        LOGGER.debug(MY_SEP)

        shotgun_inst = sgtk.api.shotgun.connection.get_sg_connection()
        sg_filters = [['project.Project.name', 'is', project_name]]
        sg_fields = [
            'id',
            'code',
            'project',
            'sg_ss_tools_repo',
            'sg_ss_tools_repo_custom_path',
            'windows_path'
        ]
        sgtk_configs = shotgun_inst.find(
            'PipelineConfiguration',
            sg_filters,
            sg_fields
        )

        wanted_repo_key = None

        sg_auth = sgtk.get_authenticated_user()
        sgtk_core_user = sg_auth.login

        sgtk_module_path = sgtk.get_sgtk_module_path()
        if '\\' in sgtk_module_path:
            sgtk_module_path = sgtk_module_path.replace('\\', '/')
        sgtk_cfg_path = '/'.join(sgtk_module_path.split('/')[:5])
        LOGGER.debug('sgtk_module_path >> {}'.format(sgtk_module_path))
        LOGGER.debug('sgtk_cfg_path >> {}'.format(sgtk_cfg_path))

        for my_config in sgtk_configs:
            my_config_repo_key = my_config['sg_ss_tools_repo']
            my_config_repo_custom = my_config['sg_ss_tools_repo_custom_path']
            my_config_path = my_config['windows_path']
            if '\\' in my_config_path:
                my_config_path = my_config_path.replace('\\', '/')
                if my_config_path == sgtk_cfg_path:
                    wanted_repo_key = my_config_repo_key
                    m = 'wanted_repo_key >> {}'.format(wanted_repo_key)
                    LOGGER.debug(m)
                    break

        if wanted_repo_key:
            if wanted_repo_key == 'custom':
                # --- For developers to point to *any* pipeline code repository
                # --- as specified in the called Shotgun configuration...
                repo_path = my_config_repo_custom

                if '\\' in repo_path:
                    repo_path = repo_path.replace('\\', '/')

                if repo_path.endswith('/'):
                    repo_path = repo_path.strip('/')

                if not os.path.exists(repo_path):
                    m = 'Custom path does not exist! >> {}'.format(repo_path)
                    raise tank.TankError(m)
            elif wanted_repo_key == 'dev':
                # --- For developers to do individual tesing against clones of
                # --- same-named repositories within their X:/dev location...
                repo_path = 'X:/dev/ss_dev_{0}/{1}_repo'.format(
                    sgtk_core_user,
                    project_name
                )
                # --- If it's not a Project-specific repo, we have to resort
                # --- to the generic studio repo...
                if not os.path.exists(repo_path):
                    repo_path = 'X:/dev/ss_dev_{0}/ss_studio_repo'.format(
                        sgtk_core_user,
                        project_name
                    )
            elif wanted_repo_key == 'project':
                # --- For everyone to launch using a Project-specific repo...
                repo_path = 'X:/tools/projects/{0}/{0}_repo'.format(
                    project_name
                )
            else:
                # --- For everyone to launch using the generic studio repo...
                repo_path = 'X:/tools/ss_studio_repo'
        LOGGER.debug(MY_SEP)

        # --- Check to make sure the resolved path, whatever it is, still
        # --- exists at the given location...
        # if not os.path.exists(repo_path):
        #     m = 'Resolved path does not exist! >> {}'.format(repo_path)
        #     raise tank.TankError(m)

        return repo_path

    def _tk_maya_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching a Maya session.
        """
        _setup = '_tk_maya_env_setup'
        self._headers(_setup)

        maya_script_paths = []
        maya_script_paths.append(
            '{}/maya/scripts/mel'.format(self._repo_path)
        )
        maya_script_paths.append(
            '{}/maya/scripts/vtool'.format(self._repo_path)
        )
        maya_script_paths.append(
            '{}/maya/scripts/mel/anim'.format(self._repo_path)
        )
        maya_script_paths.append(
            '{}/maya/scripts/mel/light'.format(self._repo_path)
        )
        maya_script_paths.append(
            '{}/maya/scripts/mel/modeling'.format(self._repo_path)
        )
        maya_script_paths.append(
            '{}/maya/scripts/mel/rigging'.format(self._repo_path)
        )
        os.environ['MAYA_SCRIPT_PATH'] = ';'.join(maya_script_paths)

        maya_tool_path = '{}/maya/scripts'.format(self._repo_path)
        module_path = '{}/maya/modules'.format(self._repo_path)
        plugin_path = '{}/maya/plug-ins'.format(self._repo_path)

        script_paths = []
        script_paths.append(self._sg_a3_path)
        script_paths.append(maya_tool_path)
        for script_path in script_paths:
            sys.path.insert(0, script_path)

        for script_path in script_paths:
            old_py_path = os.environ['PYTHONPATH']
            if script_path in old_py_path:
                m = 'Found {} in PYTHONPATH, no need to add it.'.format(
                    script_path
                )
                LOGGER.debug(m)
            else:
                LOGGER.debug('old_py_path > {}'.format(old_py_path))
                old_py_path_bits = old_py_path.split(';')

                old_py_path_bits.insert(0, script_path)
                new_py_path = ';'.join(old_py_path_bits)

                LOGGER.debug('new_py_path > {}'.format(new_py_path))
                os.environ['PYTHONPATH'] = new_py_path

        import python
        reload(python)

        # --- specific related to Maya versions...
        module_path = '{0}{1}{2}'.format(module_path, os.sep, self._version)
        LOGGER.debug('module_path > {}'.format(module_path))

        if self._version in ['2018', '2020']:
            # --- General plugins...
            os.environ['MAYA_PLUG_IN_PATH'] = '{0}{1}{2}'.format(
                plugin_path,
                os.sep,
                self._version
            )

            # --- Arnold (experimental *NOT CALLED BY ANYTHING YET*
            # --- ~ DW 202-07-13)
            wpf_root = 'C:{}Program Files'.format(os.sep)
            arnold_home = 'C:{0}solidangle{0}mtoadeploy{0}{1}'.format(
                os.sep,
                self._version
            )
            if self._version == '2020':
                arnold_home = '{0}{1}Autodesk{1}Arnold{1}maya{2}'.format(
                    wpf_root,
                    os.sep,
                    self._version
                )

            arnold_bin = '{0}{1}bin'.format(
                arnold_home,
                os.sep
            )
            LOGGER.debug('arnold_bin > {}'.format(arnold_bin))
            # TODO

            # --- VRay (legacy, we don't actually use it,
            # --- but maybe for retrieving old Assets?)...
            vray_home = '{0}{1}Autodesk{1}Maya{2}{1}vray'.format(
                wpf_root,
                os.sep,
                self._version
            )
            v_main_key = 'VRAY_FOR_MAYA{}_MAIN_x64'.format(self._version)
            os.environ[v_main_key] = vray_home
            v_plug_key =  'VRAY_FOR_MAYA{}_PLUGINS_x64'.format(self._version)
            os.environ[v_plug_key] = '{0}{1}{2}'.format(
                vray_home,
                os.sep,
                'vrayplugins'
            )

            v_root = '{0}{1}Chaos Group{1}V-Ray{1}Maya {2} for x64'.format(
                wpf_root,
                os.sep,
                self._version
            )
            v_tools_key = 'VRAY_TOOLS_MAYA{}_x64'.format(self._version)
            os.environ[v_tools_key] = '{0}{1}bin'.format(
                v_root,
                os.sep
            )
            v_osl_key = 'VRAY_OSL_PATH_MAYA{}_x64'.format(self._version)
            os.environ[v_osl_key] = '{0}{1}opensl'.format(
                v_root,
                os.sep
            )

            # --- Yeti...
            yeti_vers = 'v3.1.10'
            if self._version == '2020':
                # yeti_vers = 'v3.6.2'
                yeti_vers = 'v3.7.0'

            yeti_home = '{1}{0}yeti{0}{2}'.format(
                os.sep,
                module_path,
                yeti_vers
            )
            LOGGER.debug('yeti_home > {}'.format(yeti_home))

            os.environ['YETI_HOME'] = yeti_home
            os.environ['PATH'] = '{0}{1}{2}{3}bin'.format(
                os.environ['PATH'],
                os.pathsep,
                yeti_home,
                os.sep
            )
            os.environ['XBMLANGPATH'] = '{0}{1}{2}{3}icons'.format(
                os.environ['XBMLANGPATH'],
                os.pathsep,
                yeti_home,
                os.sep
            )
            os.environ['MAYA_PLUG_IN_PATH'] = '{0}{1}{2}{3}plug-ins'.format(
                os.environ['MAYA_PLUG_IN_PATH'],
                os.pathsep,
                yeti_home,
                os.sep
            )
            os.environ['MAYA_SCRIPT_PATH'] = '{0}{1}{2}{3}scripts'.format(
                os.environ['MAYA_SCRIPT_PATH'],
                os.pathsep,
                yeti_home,
                os.sep
            )

            if 'VRAY_PLUGINS_x64' in os.environ.keys():
                os.environ['VRAY_PLUGINS_x64'] = '{0}{1}{2}{3}bin'.format(
                    os.environ['VRAY_PLUGINS_x64'],
                    os.pathsep,
                    yeti_home,
                    os.sep
                )
            else:
                os.environ['VRAY_PLUGINS_x64'] = '{0}{1}bin'.format(
                    yeti_home,
                    os.sep
                )

            # --- Needed to get the module path in, as earlier just defines
            # --- the local Vray install path initially (DW 2020-07-09)
            if v_plug_key in os.environ.keys():
                os.environ[v_plug_key] = '{0}{1}{2}{3}bin'.format(
                    os.environ[v_plug_key],
                    os.pathsep,
                    yeti_home,
                    os.sep
                )
            else:
                os.environ[v_plug_key] = '{0}{1}bin'.format(yeti_home, os.sep)
            # --- ^^^

            y_arn_keys = [
                'ARNOLD_PLUGIN_PATH',
                'MTOA_EXTENSIONS_PATH'
            ]
            for y_arn_key in y_arn_keys:
                sub_dir = ''
                if y_arn_key == y_arn_keys[0]:
                    sub_dir = 'bin'
                if y_arn_key == y_arn_keys[1]:
                    sub_dir = 'plug-ins'

                if y_arn_key in os.environ.keys():
                    os.environ[y_arn_key] = '{0}{1}{2}{3}{4}'.format(
                        os.environ[y_arn_key],
                        os.pathsep,
                        yeti_home,
                        os.sep,
                        sub_dir
                    )
                else:
                    os.environ[y_arn_key] = '{0}{1}{2}'.format(
                        yeti_home,
                        os.sep,
                        sub_dir
                    )

            # --- SOUP OpenVDB...
            soup_openvdb_home = '{0}{1}{2}'.format(
                module_path,
                os.sep,
                'SOUPopenVDB'
            )
            LOGGER.debug('soup_openvdb_home >> {}'.format(soup_openvdb_home))
            s_arn_keys = [
                'ARNOLD_PLUGIN_PATH',
                'MTOA_EXTENSIONS_PATH'
            ]
            for s_arn_key in s_arn_keys:
                sub_dir = ''
                if s_arn_key == s_arn_keys[0]:
                    sub_dir = '{0}arnold{0}shaders'.format(os.sep)
                if s_arn_key == s_arn_keys[1]:
                    sub_dir = '{0}arnold{0}extensions'.format(os.sep)

                if s_arn_key in os.environ.keys():
                    os.environ[s_arn_key] = '{0}{1}{2}{3}'.format(
                        os.environ[s_arn_key],
                        os.pathsep,
                        soup_openvdb_home,
                        sub_dir
                    )
                else:
                    os.environ[y_arn_key] = '{0}{1}{2}'.format(
                        soup_openvdb_home,
                        sub_dir
                    )

            # --- HoudiniEngine (again more weirdness with the Maya .mod file,
            # --- which has this defined there but seems to be ignored, so we
            # --- do it here... DW 2021-03-19)
            h_ver = '18.0.597'
            h_bin = 'C:/Program Files/Side Effects Software'
            h_bin += '/Houdini {}/bin'.format(h_ver)
            if os.path.exists(h_bin):
                os.environ['PATH'] = '{0}{1}{2}'.format(
                    os.environ['PATH'],
                    os.pathsep,
                    h_bin
                )

            # --- Module path wrap-up (additions should be placed in
            # --- 'add_modules' *NOT* 'main_module_list')...
            main_module_list = [
                module_path,
                yeti_home
            ]

            add_modules = [
                'brSmoothWeights',
                'iDeform',
                'AtomsMaya',
                'ziva',
                'SOUPopenVDB',
                'houdiniEngine',
                'MayaBonusTools'
            ]

            for add_module in add_modules:
                _home = '{0}{1}{2}'.format(module_path, os.sep, add_module)
                main_module_list.append(_home)
                LOGGER.debug('Added Maya module > {}'.format(_home))

            maya_module_path = (os.pathsep).join(main_module_list)
            LOGGER.debug('maya_module_path > {}'.format(maya_module_path))

            os.environ['MAYA_MODULE_PATH'] = maya_module_path

            # --- Legacy vtool stuff, need to revisit/update/remove possibly...
            vtool_legacy_path = 'X:/tools/sinking_ship/maya/scripts/vtool'
            os.environ['PATH'] = '{0}{1}{2}'.format(
                os.environ['PATH'],
                os.pathsep,
                vtool_legacy_path
            )

            # --- Redshift (legacy, we don't actually use it,
            # --- but maybe for retrieving old Assets?)...
            r_core = 'C:/ProgramData/Redshift'
            r_plug_maya = '{}/Plugins/Maya'.format(r_core)
            r_common = '{}/Common'.format(r_plug_maya)

            os.environ['REDSHIFT_COREDATAPATH'] = r_core
            os.environ['REDSHIFT_PLUG_IN_PATH'] = '{0}/{1}/nt-x86-64'.format(
                r_plug_maya,
                self._version
            )
            os.environ['REDSHIFT_SCRIPT_PATH'] = '{}/scripts'.format(r_common)
            os.environ['REDSHIFT_XBMLANGPATH'] = '{}/icons'.format(r_common)
            os.environ['REDSHIFT_RENDER_DESC_PATH'] = '{}/rendererDesc'.format(
                r_common
            )
            _rctp = 'REDSHIFT_CUSTOM_TEMPLATE_PATH'
            os.environ[_rctp] = '{}/scripts/NETemplate'.format(r_common)
            _rmep = 'REDSHIFT_MAYAEXTENSIONSPATH'
            os.environ[_rmep] = '{0}/{1}/nt-x86-64/extensions'.format(
                r_plug_maya,
                self._version
            )
            os.environ['REDSHIFT_PROCEDURALSPATH'] = '{}/Procedural'.format(
                r_core
            )

            # --- Arnold PATH cleanup at the end...
            self._maya_arnold_version_bin_fix()
        else:
            m = 'No Maya version specific environment variables required.'
            LOGGER.debug(m)


        # - Run cg factory path setup.
        self._tk_maya_cgFactory_env_setup()

        # --- Tell the user what's up...
        self.env_paths_sanity_check()


    def _tk_maya_cgFactory_env_setup(self):
        r"""Add Maya environment relative to cg_factory submodule."""
        def appendToEnv(envVar, *paths):
            # - Convert given paths to system default.
            paths = [os.path.normpath(p) for p in paths]

            # - If var is not already in env, make it.
            if envVar not in os.environ:
                os.environ[envVar] = os.pathsep.join(paths)
                return

            # - If env has envVar update paths to system default
            envPaths = [os.path.normpath(ep) for ep in os.environ[envVar].split(os.pathsep)]
            # add each path as necessary
            for path in paths:
                # check if path already in values
                if path not in envPaths:
                    # os.environ[envVar] += os.pathsep+path
                    os.environ[envVar] =  os.environ[envVar] + os.pathsep+path
        # [end] appendToEnv

        CG_FACTORY_PATH = os.path.join(self._repo_path, 'maya/cg_factory/')

        # - Environment data.
        envDict = {
            'CG_FACTORY_PATH':[
                CG_FACTORY_PATH,
            ],
            'PYTHONPATH':[
                CG_FACTORY_PATH,
                CG_FACTORY_PATH+'mayaConfigs/mayapy-extras/site-packages',
                CG_FACTORY_PATH+'mayaConfigs/scripts',
                CG_FACTORY_PATH+'assetPipeline',
                CG_FACTORY_PATH+'riggingPipeline',
                CG_FACTORY_PATH+'textureShadingPipeline',
            ],
            'MAYA_SCRIPT_PATH':[
                CG_FACTORY_PATH,
                CG_FACTORY_PATH+'mayaConfigs/scripts'
            ],
            'XBMLANGPATH':[
                CG_FACTORY_PATH+'mayaConfigs/icons'
            ],
            'MAYA_PLUG_IN_PATH':[
                CG_FACTORY_PATH + 'mayaConfigs/plugins' # for python and root for mlls.
            ],
            'MAYA_MODULE_PATH':[
                CG_FACTORY_PATH + 'mayaConfigs/modules'
            ],
        }

        # - Include plugin maya version if folder exists.
        mllDir = os.path.join(envDict['MAYA_PLUG_IN_PATH'][0], self._version)
        if os.path.isdir(mllDir):
            envDict['MAYA_PLUG_IN_PATH'].append(mllDir)

        # - Add environments to system
        for envK,envV in envDict.items():
            appendToEnv(envK, *envV)

        #NOTE:
        #
        # do not try to get a python debugger (ie pdb trace). does not work
        # with shotgun launcher.


    def _tk_nuke_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching a Nuke session.
        """
        _setup = '_tk_nuke_env_setup'
        self._headers(_setup)

        # Update the sys.path 
        script_paths = []
        script_paths.append(self._sg_a3_path)
        for script_path in script_paths:
            sys.path.insert(0, script_path)

        # Update the NUKE_PATH
        # - Previously, the I.T. department was configuring machines with the NUKE_PATH already set to 'x:\tools\nuke'
        # - This is now legacy and will be ignored when we launch nuke via the sgtk
        # - Also, log a warning if any NUKE_PATH already exists that is not a part of the expected "sgtk" launch mechanism

        # Update the NUKE_PATH
        # - Previously, the I.T. department was configuring machines with the NUKE_PATH already set to 'x:\tools\nuke'
        # - This is now legacy and will be ignored when we launch nuke via the sgtk
        # - Also, log a warning if any NUKE_PATH already exists that is not a part of the expected "sgtk" launch mechanism
        nuke_plugin_path = []

        # Process the existing NUKE_PATH
        # - this is necessary to pickup the sgtk from the existing path
        if 'NUKE_PATH' in os.environ:
            nuke_paths = os.environ['NUKE_PATH'].split(os.pathsep)
            for nuke_path in nuke_paths:
                if 'sgtk' in nuke_path:
                    nuke_plugin_path.append(nuke_path)
                else:
                    LOGGER.warn('Bad value in NUKE_PATH, ignoring: {}'.format(nuke_path))

        # Add main/dev pipeline repos to NUKE_PATH
        try:
            # old method
            sse_nuke_pipeline = '{}/nuke'.format(self._repo_path).replace('/', '\\')
            nuke_plugin_path.append(sse_nuke_pipeline)
        except:
            # new method: 
            # Only take the first entry in the list, the rest are fallbacks and are irrelevant for nuke.
            sse_nuke_pipeline = '{}/nuke'.format(self._repo_paths[0]).replace('/', '\\')
            nuke_plugin_path.append(sse_nuke_pipeline)
            
        LOGGER.debug('Setting NUKE_PATH in os.environ...')
        os.environ['NUKE_PATH'] = os.pathsep.join(nuke_plugin_path)
         
        # Update SSE nuke tools paths
        # 1) SSE_NUKE_PIPELINE 
        #    - location of TD controlled pipeline scripts/tools/templates/etc
        #    - This should match the location of the currently selected repo (self._repo_paths[0])
        #
        # 2) SSE_NUKE_TOOLS
        #    - location of ARTIST controlled scripts/tools/templates/etc
        #    - For now, this is hard coded.
        #         
        # TODO: support mac/linux paths?
        #
        LOGGER.debug('Setting SSE_NUKE_PIPELINE in os.environ...')
        os.environ['SSE_NUKE_PIPELINE'] = sse_nuke_pipeline

        LOGGER.debug('Setting SSE_NUKE_TOOLS in os.environ...')
        os.environ['SSE_NUKE_TOOLS'] = "N:\\Resources\\Tools\\Nuke\\StudioTools"

        # Prevent python from writing bytecode (avoids .pyc files)
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

    def _tk_aftereffects_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching an AE session.
        """
        _setup = '_tk_aftereffects_env_setup'
        self._headers(_setup)

        script_paths = []
        script_paths.append(self._sg_a3_path)
        for script_path in script_paths:
            sys.path.insert(0, script_path)

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

    def _tk_houdini_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching a Houdini session.
        """
        _setup = '_tk_houdini_env_setup'
        self._headers(_setup)

        #script_paths = []
        #script_paths.append(self._sg_a3_path)
        
        #for script_path in script_paths:
        #    sys.path.insert(0, script_path)

        # --- OCIO/ACES...
        os.environ['OCIO'] = OCIO_CONFIG
        os.environ['OCIO_ACTIVE_DISPLAYS'] = 'ACES'
        os.environ['OCIO_ACTIVE_VIEWS'] = 'Rec.709:sRGB:Raw:Log'
        os.environ['HOUDINI_OCIO_SRGB_FILE_COLORSPACE'] = \
            'Utility - Linear - sRGB'

        # --- houdini pipeline path
        houdini_path = os.environ["HOUDINI_PATH"]
        
        # adding studio repo_path
        os.environ['HOUDINI_PATH'] = "{0}{1}{2}".format(houdini_path, ';', \
            '{}/houdini/'.format(self._repo_path))

        # sg api3 to houdini
        # test purpose - replacing sys.path insertion for pythonpath
        os.environ['PYTHONPATH'] = "{0}{1}{2}".format(os.environ["PYTHONPATH"], ';', \
            '{}'.format(self._sg_a3_path))

        LOGGER.debug("New HOUDINI_PATH > {}".format( os.environ["HOUDINI_PATH"]))

        # --- For test purpose using htoA...
        # replace houdini version - hard coding.
        
        #htoa_path = "{}".format("N:/projects/RnD/Arnold_for_Houdini/htoa-5.6.1.0_rf9edb5c_houdini-18.5.532_windows/htoa-5.6.1.0_rf9edb5c_houdini-houdini-18.5.532")
        #os.environ['PYTHONPATH'] = "{0}{1}{2}".format(os.environ["PYTHONPATH"], ';', \
        #    '{}/scripts/bin/'.format(htoa_path))
        
        #os.environ['HOUDINI_PATH'] = "{0}{1}{2}".format(os.environ["HOUDINI_PATH"], ';', \
        #    '{}'.format(htoa_path))

        # --- Tell the user what's up...
        self.env_paths_sanity_check()


    def _tk_natron_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching a Houdini session.
        """
        _setup = '_tk_natron_env_setup'
        self._headers(_setup)

        script_paths = []

        # --- NOTE: switch to the commented out line in the near future,
        # ---       'X:/tools/natron' is temporary...
        # studio_na_root='{}/natron'.format(self._repo_path).replace('/','\\')
        studio_na_root = 'X:/tools/natron'
        script_paths.append(studio_na_root)
        script_paths.append('{}/tools_sse'.format(studio_na_root))
        script_paths.append('{}/tools_sse/Plugins'.format(studio_na_root))
        script_paths.append(self._sg_a3_path)
        studio_na_paths = os.pathsep.join(script_paths)

        if 'NATRON_PLUGIN_PATH' in os.environ:
            LOGGER.debug('Found existing NATRON_PLUGIN_PATH in os.environ...')
            os.environ['NATRON_PLUGIN_PATH'] = os.pathsep.join(
                [
                    studio_na_paths,
                    os.environ['NATRON_PLUGIN_PATH']
                ]
            )
        else:
            m = 'No existing NATRON_PLUGIN_PATH in os.environ, creating...'
            LOGGER.debug(m)
            os.environ['NATRON_PLUGIN_PATH'] = '{}'.format(studio_na_paths)

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

    def _headers(self, user_title):
        """
        Print strings formatted as headers (with
        emphasis) to the console.
        @param str user_title: The title as a string to
                               fromat and print as a
                               header.
        """
        if user_title:
            LOGGER.debug(MY_SEP)
            LOGGER.debug(user_title)
            LOGGER.debug(MY_SEP)
        else:
            LOGGER.debug('Please provide a title string.')

    def env_paths_sanity_check(self):
        """
        Print the lists of source paths to the Shotgun
        Desktop Console.
        @param str engine_setup: represents the DCC setup
                                 we want to check against,
                                 which may have unique
                                 path variables.
        """
        env_var_str = []

        path_list = [
            'PATH',
            'SYS.PATH',
            'PYTHONPATH',
        ]

        # --- Per engine checks if required...
        if self._engine_name == 'tk-maya':
            _maya_paths = [
                'MAYA_MODULE_PATH',
                'MAYA_PLUG_IN_PATH',
                'MAYA_SCRIPT_PATH'
            ]

            path_list.extend(_maya_paths)

        if self._engine_name == 'tk-nuke':
            _nuke_paths = [
                'NUKE_PATH'
            ]
            path_list.extend(_nuke_paths)

        if self._engine_name == 'tk-aftereffects':
            pass

        if self._engine_name == 'tk-houdini':
            _houdini_paths = [
                'HOUDINI_PATH'
            ]
            path_list.extend(_houdini_paths)

        if self._engine_name == 'tk-natron':
            _natron_paths = [
                'NATRON_PLUGIN_PATH',
            ]
            path_list.extend(_natron_paths)

        # --- Iterate over the paths...
        for path_item in path_list:
            env_var_str.append(MY_SEP)
            env_var_str.append(path_item)
            env_var_str.append(MY_SEP)

            if path_item == 'SYS.PATH':
                for item in sys.path:
                    env_var_str.append(item)
            else:
                for item in os.environ[path_item].split(';'):
                    env_var_str.append(item)

        env_var_str.append(MY_SEP)

        for env_var_item in env_var_str:
            LOGGER.debug(env_var_item)

    def _maya_arnold_version_bin_fix(self):
        """
        Get rid of the bad Arnold bin path from the PATH (mystery where it's
        coming from).
        """
        if self._version != '2018':
            bad_path = 'C:{0}solidangle{0}mtoadeploy{0}2018{0}bin'.format(
                os.sep
            )

            _os_env_paths = os.environ['PATH'].split(';')
            if bad_path in _os_env_paths:
                _os_env_paths.remove(bad_path)
                LOGGER.debug('Removed from PATH >> {}'.format(bad_path))
                _os_env_path_str = os.pathsep.join(_os_env_paths)
                os.environ['PATH'] = _os_env_path_str
# ---eof
