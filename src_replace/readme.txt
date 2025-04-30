# Instructions for Enhancing Pluto Compiler Functionality

1. Move the `src_replace` directory into the Pluto compiler folder:
    ```
    mv src_replace pluto-0.11.4/
    ```

2. Navigate to the Pluto compiler folder:
    ```
    cd pluto-0.11.4/
    ```

3. Run the `replace.sh` script to enhance Pluto's functionality:
    ```
    cd src_replace/
    bash replace.sh
    cd ..
    ```

4. Create a folder for your test cases:
    ```
    mkdir your_test/
    ```

5. Place your kernel file (e.g., `your_kernel.c`) into the `your_test` folder.

6. Generate the polyhedral model using the Pluto compiler:
    ```
    cd your_test/
    ../polycc your_kernel.c
    ```

# Notes:
- Ensure that the Pluto compiler is installed before running these steps.
- The `replace.sh` script modifies or enhances Pluto's functionality. Refer to the official documentation for details.
- The kernel file should be a valid C program that you want to analyze or optimize.
