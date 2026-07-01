# Trust-me-I-know-the-path

## How to use git

* Download file

In a bash terminal:
``` bash
git clone https://gitlab.lrz.de/pcn_2026_group_2/trust-me-i-know-the-path.git
```
* File upload
``` bash
git add .
git commit -m "Commend here"
git push
```


## Step-by-Step Execution Guide

Open Linux Terminator
* Navigate to the project root directory:
```bash
cd /home/... .../trust-me-i-know-the-path
```
* Start the Ryu Controller
```bash
ryu-manager --observe-links controller.py
```
* Launch the Mininet Topology

Open a new Terminator window by <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>T</kbd>
``` bash
sudo python3 run_tutorial.py
```
* Setup Host h1

In mininet window:
```plaintext
mininet> h1 xterm &
```
Inside the h1 xterm window: (paste key: <kbd>Shift</kbd> + <kbd>Ins</kbd>)
``` bash
python3 host1.py
```
* Setup Host h2

In mininet window:
```plaintext
mininet> h2 xterm &
```
Inside the h2 xterm window:
``` bash
python3 host2.py
```

* Restart Network
In mininet window:
``` bash
mininet> exit
sudo mn -c
```
Then start the Ryu Controller again.

* Monitor Network Traffic (Optional)

open another new terminator window
``` bash
sudo wireshark &
```

