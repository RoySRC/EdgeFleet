from __future__ import annotations

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

from examples.use_cases.catalog import CATEGORIES, USE_CASES
from examples.use_cases.programs import program_for


class EdgeFleetUseCasesDirective(SphinxDirective):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {"show-notes": directives.flag}
    has_content = False

    def run(self) -> list[nodes.Node]:
        category = self.arguments[0]
        if category not in CATEGORIES:
            raise self.error(
                f"Unknown use-case category {category!r}. "
                f"Expected one of: {', '.join(CATEGORIES)}"
            )
        cases = [case for case in USE_CASES if case.category == category]
        output: list[nodes.Node] = []
        summary = nodes.paragraph(
            text=(
                f"This page contains {len(cases)} example programs. "
                "Replace target agent IDs, skills, credentials, and context "
                "with deployment-specific values."
            )
        )
        output.append(summary)

        for case in cases:
            section = nodes.section(ids=[case.slug])
            section += nodes.title(text=case.title)
            metadata = nodes.paragraph()
            metadata += nodes.strong(text="Example profile: ")
            metadata += nodes.Text(
                f"agent={case.target_agent}, skill={case.skill}, "
                f"reasoning={case.mode}, actions={case.allow_actions}."
            )
            section += metadata

            program = program_for(case)
            code = nodes.literal_block(program, program)
            code["language"] = "python"
            code["linenos"] = False
            section += code

            if case.note and "show-notes" in self.options:
                note = nodes.note()
                note += nodes.paragraph(text=case.note)
                section += note
            output.append(section)
        return output


def setup(app: Sphinx) -> dict[str, object]:
    app.add_directive(
        "edgefleet-use-cases", EdgeFleetUseCasesDirective
    )
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }

