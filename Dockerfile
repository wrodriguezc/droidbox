FROM honeynet/droidbox

LABEL maintainer="wrodriguezc@ucenfotec.ac.cr"

#Update run file from parent container
ADD run.sh /build/

#Setup SSH server
RUN apt-get update && apt-get install -y openssh-server
RUN mkdir /var/run/sshd
RUN sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN echo "PermitUserEnvironment yes" >> /etc/ssh/sshd_config
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

#Set ENV for SSH connections
RUN echo 'declare -x LC_ALL="C"' >> /root/.bashrc
RUN echo 'declare -x DEBIAN_FRONTEND="noninteractive"' >> /root/.bashrc
RUN echo 'declare -x JAVA_HOME="/usr/lib/jvm/java-7-openjdk-amd64/"' >> /root/.bashrc
RUN echo 'declare -x ANDROID_HOME="/opt/android-sdk-linux"' >> /root/.bashrc
RUN echo 'declare -x ANDROID_SDK_HOME="/opt/android-sdk-linux"' >> /root/.bashrc
RUN echo 'declare -x PATH="${PATH}:$JAVA_HOME/bin:${ANDROID_HOME}/tools:${ANDROID_HOME}/platform-tools"' >> /root/.bashrc
RUN echo 'declare -x sv="r24.4.1"' >> /root/.bashrc
RUN echo 'declare -x TERM=linux' >> /root/.bashrc
RUN echo 'declare -x TERMINFO=/etc/terminfo' >> /root/.bashrc

#Patch .bashrc
RUN sed -i 's/\[ \-z \"\$PS1\" \] \&\& return/#/' /root/.bashrc

#Patch .profile
RUN echo 'if [ -f ~/.bashrc ]; then\n\t. ~/.bashrc\nfi' > /root/.profile

#Setup SSH access
RUN mkdir --mode=700 /root/.ssh
COPY id_rsa.pub /root/
RUN cat /root/id_rsa.pub >> /root/.ssh/authorized_keys
RUN chmod 600 /root/.ssh/authorized_keys
RUN rm /root/id_rsa.pub

#SSH PORT
EXPOSE 22

#VNC PORT
EXPOSE 5900

#start the SSH service
CMD ["/usr/sbin/sshd", "-D"]

#Override the parent entrypoint
ENTRYPOINT [""]
