# Tetration Policy Client (Python)

This is an example Tetration policy client written in Python

To connect and print incoming policies
```bash
# clone this repository
git clone https://github.com/tetration-exchange/pol-client-python.git && cd pol-client-python

# install dependencies
pip install -r requirements.txt

# copy your policy data tap credentials (download in "certificate" format)
cp /path/to/downloaded/Policy-Stream-${tenant-id}-${tenant-name}.cert.tar.gz ./credentials.tar.gz

# make the credentials directory and unzip keys and certificates
mkdir credentials
tar -xzvf credentials.tar.gz -C credentials

# run the client - python 3 required!
python client.py
```

### Advanced Usage
By default, the client will print updates to the screen and also log to file

You can also choose to output updates as binary blobs or JSON text files
    
A simple example to read the binary messages is found in `reader.py` 


## License

Please refer to the file *LICENSE.pdf* in same directory of this README file.