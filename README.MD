Setup project:
1. Create virtual environment 
    ```python -m venv venv```
2. Activate the virtual environment .\venv\Scripts\activate
   ```.\venv\Scripts\activate```
3. Install project dependencies
   ```pip install -r requirements.txt```

Run tests:
1. Ensure the virtual environment is activated
    ```.\venv\Scripts\activate```
2. Run all tests using pytest
    ```pytest tests```
3. Run specific tests using pytest
    ```pytest tests/test_specific_file.py::TestClass::test_method```