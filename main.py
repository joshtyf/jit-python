import asyncio
import json
import logging
import os
import textwrap
import warnings
from typing import Any

from google.adk import Agent
from google.adk.errors import already_exists_error
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.skills import models
from google.adk.tools import AgentTool, google_search
from google.adk.tools.skill_toolset import SkillToolset
from google.genai import types
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logging.getLogger("google_adk").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

APP_NAME = "jit_python"
USER_ID = "user_id"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")


class MethodGenInput(BaseModel):
    method_name: str
    method_description: str | None = None
    feedback: str | None = None


class MethodGenOutput(BaseModel):
    method_code: str


pip_install_skill = models.Skill(
    frontmatter=models.Frontmatter(
        name="pip-install-skill",
        description="A skill that demonstrates how to write the code that uses pip install at runtime",
    ),
    instructions=textwrap.dedent(
        """
        To install a pip package dynamically at runtime from within a generated method,
        use the subprocess module along with sys.executable. Here is the required pattern:

        import subprocess
        import sys
        import importlib.util
        import logging

        _pip_logger = logging.getLogger('RUNTIME_PIP_INSTALLER')

        if importlib.util.find_spec('<module_name>') is None:
            _pip_logger.warning('Installing <package_name>...')
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '<package_name>'])
            _pip_logger.warning('Successfully installed <package_name>')
        else:
            _pip_logger.info('<package_name> is already installed')

        Make sure to import the installed package only after the subprocess call completes successfully.

        IMPORTANT: You MUST always include the _pip_logger.warning() calls exactly as shown above.
        Do NOT omit, replace, or skip the logging statements under any circumstances.
        """
    ),
)


class JitPython:
    def __init__(self):
        self.root_agent = Agent(
            name="root_agent",
            description="Root agent for JIT Python method generation and improvement.",
            model=GEMINI_MODEL,
            instruction=textwrap.dedent(
                """
                You are an expert software engineer with expertise in Python. You have 2 jobs:
                1. Generate Python methods dynamically based on the method name and description provided.
                2. Improve the generated methods based on user feedback to ensure they meet the requirements and are optimized for performance and readability.
                Make sure that the generated method is valid Python code and can be executed without errors.

                You have access to a Google Search tool which you can use to gather information needed for method generation.
                Use it if you need to look up anything to generate the method correctly.

                You also have access to the `pip-install-skill` which you can use to learn how to write code that installs
                pip packages at runtime in case you need to generate methods that require external dependencies.
            """  # noqa: E501
            ),
            input_schema=MethodGenInput,
            output_schema=MethodGenOutput,
            tools=[
                AgentTool(
                    Agent(
                        name="SearchAgent",
                        description="Agent for performing Google searches to gather information needed for method generation.",  # noqa: E501
                        model=GEMINI_MODEL,
                        instruction="Perform Google searches",
                        tools=[google_search],
                    )
                ),
                SkillToolset(
                    skills=[pip_install_skill],
                ),
            ],
        )
        self.memory = InMemorySessionService()
        self._methods_code: dict[str, str] = {}

    def __getattr__(self, name: str) -> Any:
        def wrapper(*args, **kwargs):
            method_description = kwargs.pop(
                "__description", "No method description provided"
            )

            method_code = asyncio.run(self._generate_method(name, method_description))
            namespace = {}
            exec(method_code, globals(), namespace)

            method = namespace.get(name)
            if not method:
                raise RuntimeError(f"Failed to generate method: {name}")

            setattr(self, name, method)
            return method(*args, **kwargs)

        return wrapper

    async def _generate_method(
        self,
        method_name: str,
        description: str | None = None,
        feedback: str | None = None,
    ) -> str:
        try:
            await self.memory.create_session(
                app_name=APP_NAME, session_id=method_name, user_id=USER_ID
            )
        except already_exists_error.AlreadyExistsError:
            pass
        runner = Runner(
            app_name=APP_NAME,
            agent=self.root_agent,
            session_service=self.memory,
        )

        query_json = json.dumps(
            {
                "method_name": method_name,
                "method_description": description,
                "feedback": feedback,
            }
        )
        user_content = types.Content(role="user", parts=[types.Part(text=query_json)])

        async for event in runner.run_async(
            user_id=USER_ID, session_id=method_name, new_message=user_content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_response_content = event.content.parts[0].text
        if isinstance(final_response_content, str):
            # Should match `MethodGenOutput` schema
            method_code = json.loads(
                final_response_content,
            ).get("method_code", "")
        else:
            raise RuntimeError(
                "Expected final response content to be a string containing JSON."
            )
        self._methods_code[method_name] = method_code
        return method_code

    def improve_method(self, method_name: str, feedback: str):
        if not hasattr(self, method_name):
            raise AttributeError(
                f"Method {method_name} does not exist and cannot be improved."
            )
        method_code = asyncio.run(self._generate_method(method_name, feedback=feedback))
        namespace = {}
        exec(method_code, globals(), namespace)
        method = namespace.get(method_name)
        if not method:
            raise RuntimeError(f"Failed to improve method: {method_name}")
        setattr(self, method_name, method)

    def get_method_code(self, method_name: str) -> str:
        if method_name not in self._methods_code:
            raise AttributeError(f"Method {method_name} does not exist.")
        return self._methods_code[method_name]
