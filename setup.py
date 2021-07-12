import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="StarData",
    version="1.0.0",
    author="zhy-uts",
    author_email="zhuhaoyu0909@icloud.com",
    description="A comprehensive simple API for general cloud database framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/underthestars-zhy/StarData-Python",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(),
    python_requires='>=3.8',
    install_requires=['requests>=2.24.0']
)