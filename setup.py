from setuptools import setup

setup(
    name="todoist-data-exporter",
    version="0.1.0",
    description="A Python tool for exporting Todoist data into CSV files for analysis and visualization.",
    author="Mark Campos",
    author_email="mark@mark.digital",
    url="https://github.com/markedwardcampos/todoist-data-exporter",
    py_modules=["exporter"],
    package_dir={"": "src"},
    install_requires=[
        "pandas>=2.0.0",
        "todoist-api-python>=4.0.0,<5"
    ],
    entry_points={
        "console_scripts": [
            "todoist-exporter=exporter:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)