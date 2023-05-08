import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="movify",
    version="0.0.1",
    author="Benjamin Jochum",
    author_email="bobboman1000@icloud.com",
    description="Package to migrate YTM library to spotify",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bobboman1000/Movify",
    project_urls={
        "Bug Tracker": "https://github.com/bobboman1000/Movify/sampleproject/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"movify": "movify"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.6",
)
