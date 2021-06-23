# This file is based on templates provided and copyrighted by Autodesk, Inc.
# This file has been modified by Epic Games, Inc. and is subject to the license 
# file included in this repository.

"""
Hook that loads defines all the available actions, broken down by publish type.
"""

import pprint
import os
import sgtk
import unreal
import re

HookBaseClass = sgtk.get_hook_baseclass()


class UnrealActions(HookBaseClass):

    ##############################################################################################################
    # public interface - to be overridden by deriving classes

    def _import_to_content_browser(self, path, sg_publish_data):
        """
        Import the asset into the Unreal Content Browser.

        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        """

        # --- SSE: Use custom framework when loading in content. -AB (2021-06-11)
        imgspc_fw = self.load_framework("tk-framework-imgspc")
        imgspc_ue_imp = imgspc_fw.import_module("unreal.import_utils")
        imgspc_ue_imp.import_to_content_browser(path, sg_publish_data)
