# Create your public ssh key

1. open terminal on mac or Powershell on Windows and type:
```
ssh-keygen -t rsa
```
This starts the key generation process. When you execute this command, the ```ssh-keygen``` utility prompts you to indicate where to store the key and how to name it.
2. Press the ENTER key to accept the default location. The ssh-keygen utility prompts you for a passphrase. REMEBER THE PASSPHRASE!!!
3. Type in a passphrase.
4. After you confirm the passphrase, the system generates the key pair.
```
Your identification has been saved in /Users/myname/.ssh/hackathon
Your public key has been saved in /Users/myname/.ssh/hackathon.pub.
The key fingerprint is:
ae:89:72:0b:85:da:5a:f4:7c:1f:c2:43:fd:c6:44:38 myname@mymac.local
The key's randomart image is:
+--[ RSA 2048]----+
|                 |
|         .       |
|        E .      |
|   .   . o       |
|  o . . S .      |
| + + o . +       |
|. + o = o +      |
| o...o * o       |
|.  oo.o .        |
+-----------------+
```

Your public key is saved to the ```hackathon.pub``` file and is the key you upload hackathon orhanizers.

# Access your virtual machine
The organizers will send you the command that would be similar to this one
```
ssh  name@195.242.24.222 -i private_key
```
Enter your passphrase when prompted


# Install NVIDIA container toolkit
1. Configure the production repository:
```
$ curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
``` 
2. Update the packages list from the repository:
```
$ sudo apt-get update
```
3. Install the NVIDIA Container Toolkit packages:
```
$ sudo apt-get install -y nvidia-container-toolkit
```
# Check the docker
1 . Create the docker group if it does not exist
```
$ sudo groupadd docker
```
2. Add your user to the docker group.
```
$ sudo usermod -aG docker $USER
```
3. Log in to the new docker group (to avoid having to log out / log in again; but if not enough, try to reboot):
```
$ newgrp docker
```
4. Check if docker can be run without root
```
$ docker run hello-world
```

# install ollama
```
docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```
# run llama3 via ollama
```
docker exec -it ollama ollama run llama2
```
