from setuptools import setup, find_packages

setup(
    name="doc_classification_mmbb",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'Pillow==10.3.0',
        'PyMuPDF==1.24.1',
        'anthropic==0.25.1',
        'numpy==1.26.4',
        'opencv-python==4.9.0.80',
        'pyodbc',
        'azure-identity',
        'pytest'
    ],
    python_requires='>=3.12',  # Since you're using Python 3.12.4
    author="",
    author_email="",
    description="Document Classification for Mobility Budget",
    keywords="document, classification, mobility budget",
)