import mkdocs_gen_files
import sys
from pathlib import Path

SOURCE_DIR = "source"
REFERENCE_HEADING = "reference"

# Source located in ../../source from the current directory
ROOT_SOURCE_PATH = (Path(__file__).parent / ".." / SOURCE_DIR).resolve()

# This is really cheating, but it should be safe for almost every project.
# Instead of getting the project modules from our virtual environment, we make sure we use the source directory.
# If another version of the project is already installed, this should ensure we override it with this local copy.
sys.path.insert(0, str(ROOT_SOURCE_PATH))


for file in sorted(ROOT_SOURCE_PATH.iterdir()):
    # Don't document the "tests" module.
    if file.name not in ("test", "tests", "testing"):
        for module_path in sorted(file.rglob("*.py")):

            module_relative_path = module_path.relative_to(ROOT_SOURCE_PATH)

            module_path_parts = list(module_relative_path.with_suffix("").parts)
            doc_path_parts = module_path_parts

            if module_path_parts[-1] == "__init__":
                # Don't document __init__.py files if they are empty.
                if not module_path.read_text().strip():
                    continue
                module_path_parts = module_path_parts[:-1]
                doc_path_parts[-1] = "Overview"

            elif module_path_parts[-1] == "__main__":
                continue

            # This is rather redundant since it is the root namespace of 95% of our code.
            if doc_path_parts[0] == "habitatenergy":
                doc_path_parts = doc_path_parts[1:]

            # Write the markdown file
            doc_path = Path(REFERENCE_HEADING, *doc_path_parts).with_suffix(".md")
            module_name = ".".join(module_path_parts)
            with mkdocs_gen_files.open(doc_path, "w") as fd:
                page = f"`{module_name}`\n\n::: {module_name}\n"
                fd.write(page)

            # Ensure the "edit" link correctly links to the python file, not the dynamic markdown file
            mkdocs_gen_files.set_edit_path(doc_path, Path("..", SOURCE_DIR, module_relative_path))
