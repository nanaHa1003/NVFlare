# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import shutil
import traceback
from typing import List

from .constants import ProvisionMode, WorkDir
from .ctx import ProvisionContext
from .entity import Project
from .spec import Builder


class Provisioner:
    def __init__(self, root_dir: str, builders: List[Builder]):
        """Workflow class that drive the provision process.

        Provisioner's tasks:

            - Maintain the provision workspace folder structure;
            - Invoke Builders to generate the content of each startup kit

        ROOT_WORKSPACE Folder Structure::

            root_workspace_dir_name: this is the root of the workspace
                project_dir_name: the root dir of the project, could be named after the project
                    resources: stores resource files (templates, configs, etc.) of the Provisioner and Builders
                    prod: stores the current set of startup kits (production)
                        participate_dir: stores content files generated by builders
                    wip: stores the set of startup kits to be created (WIP)
                        participate_dir: stores content files generated by builders
                    state: stores the persistent state of the Builders

        Args:
            root_dir (str): the directory path to hold all generated or intermediate folders
            builders (List[Builder]): all builders that will be called to build the content
        """
        self.root_dir = root_dir
        self.builders = builders
        self.template = {}

    def add_template(self, template: dict):
        if not isinstance(template, dict):
            raise ValueError(f"template must be a dict but got {type(template)}")
        self.template.update(template)

    def provision(self, project: Project, mode=None):
        server = project.get_server()
        if not server:
            raise RuntimeError("missing server from the project")

        workspace_root_dir = os.path.join(self.root_dir, project.name)
        ctx = ProvisionContext(workspace_root_dir, project)
        if self.template:
            ctx.set_template(self.template)

        if not mode:
            mode = ProvisionMode.NORMAL
        ctx.set_provision_mode(mode)

        try:
            for b in self.builders:
                b.initialize(project, ctx)

            # call builders!
            for b in self.builders:
                b.build(project, ctx)

            for b in self.builders[::-1]:
                b.finalize(project, ctx)

        except Exception:
            prod_dir = ctx.get(WorkDir.CURRENT_PROD_DIR)
            if prod_dir:
                shutil.rmtree(prod_dir)
            print("Exception raised during provision.  Incomplete prod_n folder removed.")
            traceback.print_exc()
        finally:
            wip_dir = ctx.get(WorkDir.WIP)
            if wip_dir:
                shutil.rmtree(wip_dir)
        return ctx
