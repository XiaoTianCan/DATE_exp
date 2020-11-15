/*
    Description: packet sender programm running on each sender host
*/
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <errno.h>
#include <string.h> 
#include <unistd.h> 
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <linux/ip.h>
#include <linux/udp.h>
#include <pthread.h>

#define MAXPKTNUM 1000000
#define MAXHOSTNUM 30
#define MAXPATHNUM 5
#define PKT_DISTRI_PATH "env/pkt_distri.txt"
#define MAX_PKTLEN 1500
#define MIN_PKTLEN 60

typedef enum{false=0,true} bool;

float demRates[MAXHOSTNUM];
int hostId = 0;
int hostNum = 0;

int rawSock;
struct sockaddr_in addr_in;
pthread_t thread[MAXHOSTNUM];
bool sendFlag = false;

uint16_t *pktLenList;
char *TMfile = NULL;
float TMscale = 1.0;
int TMbegin = 0;
int TMend = 2;
int pktsenderPeriod = 0;
float TMs[4032][MAXHOSTNUM] = {0};

/*pseudoUDPPacket: Pseudo header needed for calculating the UDP header checksum*/
struct pseudoUDPPacket {
    uint32_t srcAddr;
    uint32_t dstAddr;
    uint8_t zero;
    uint8_t protocol;
    uint16_t UDP_len;
};

/*free_all(): free allocated memory*/
void free_all() {
    free(pktLenList);
}

/*rand_pkt_size(): just for test without *.pcap file*/
void rand_pkt_size() {
    // read pkt distri
    double cdf[MAX_PKTLEN + 1];
    int ind;
    double prob;
    memset(cdf, 0, sizeof(cdf));

    FILE *f = fopen(PKT_DISTRI_PATH, "r");
    while(fscanf(f, "%d %lf", &ind, &prob) != EOF){
        cdf[ind] = prob;
    }
    for (ind = MIN_PKTLEN + 1; ind <= MAX_PKTLEN; ind ++){
        if(cdf[ind] < cdf[ind - 1]){
            cdf[ind] = cdf[ind - 1];
        }
    }
    
    uint32_t count = 0;
    uint16_t pktLen = 1024;
    pktLenList = (uint16_t *)malloc(MAXPKTNUM*sizeof(uint16_t));
    while (count <= MAXPKTNUM) {
        // sample pktLen
        double randnum = (double)rand() / RAND_MAX;
        for (ind = MIN_PKTLEN; ind <= MAX_PKTLEN; ind ++){
            if(randnum <= cdf[ind]){
                pktLen = ind;
                break;
            }
        }
        pktLenList[count] = pktLen;
        count++;
    }
    fclose(f);
}
void read_rate_file() {
    FILE *fp = fopen(TMfile, "r");
    char tm[4000];
    float tmTmp[1000];
    int lineCount = 0;
    while(!feof(fp) && lineCount <= 4030){
        memset(tm, 0, 4000);
        fgets(tm, 4000, fp);
        char *result = NULL;
        result = strtok(tm, ",");
        int demId = 0;
        while( result != NULL ) {
            tmTmp[demId] = atof(result)/TMscale;
            demId++;
            result = strtok( NULL, "," );
        }

        demId = 0;
        for(int i = 0; i < hostNum; i++){
            if(i == hostId){
                TMs[lineCount][i] = 0.0;
            }
            else{
                TMs[lineCount][i] = tmTmp[hostId*(hostNum-1)+demId];
                demId++;
            }
        }
        lineCount++;
    }
    fclose(fp);
}

/*csum(): compute checksum from the packet*/
uint16_t csum(uint16_t *buf, int nwords)
{ 
    uint32_t sum;
    for (sum = 0; nwords > 0; nwords--)
    {
        sum += *buf++;
    }
    sum = (sum >> 16) + (sum & 0xffff);
    sum += (sum >> 16);
    return (uint16_t)(~sum);
}

/*pthread_sender(): construct UDP packet and send it to the specific dst host*/
void pthread_sender(void *arg) {
    int dstHostId = *(int*)arg;
    printf("pthread_sender:%d started\n", dstHostId);

    char dstIPStr[20] = {0};
    sprintf(dstIPStr, "10.0.0.%d", dstHostId+1);
    printf("%s\n", dstIPStr);

    // step 1: construct packet and pseudo packewt
    char packet[1600];
    memset(packet, 0, sizeof(packet));
    struct iphdr *ipHdr = (struct iphdr *) packet;;
    struct udphdr *udpHdr = (struct udphdr *) (packet + sizeof(struct iphdr));
    char *data = (char *) (packet + sizeof(struct iphdr) + sizeof(struct udphdr));

    struct pseudoUDPPacket pUDPPacket;
    char pseudo_packet[1600];

    /*init ipHdr*/
    ipHdr->ihl = 5;
    ipHdr->version = 4;
    ipHdr->tos = 0;
    ipHdr->id = htons(54321);
    ipHdr->frag_off = 0x00;
    ipHdr->ttl = 64;
    ipHdr->protocol = IPPROTO_UDP;
    /*init udpHdr*/
    udpHdr->check = 0;
    /*init pseudo packet which is used for computing checksum*/
    pUDPPacket.zero = 0;
    pUDPPacket.protocol = IPPROTO_UDP;

    
    // Step 2: start sending packets
    if (dstHostId < hostId) sleep(hostNum-dstHostId);
    else sleep(hostNum-dstHostId+1);
    uint32_t pPkt = 0;
    uint16_t srcPort = 8000, dstPort = 8000, pktLen, dataLen;
    while(!sendFlag) {
        sleep(1);
    }
    printf("Thread %d begins to send pkts\n", dstHostId);
    while(sendFlag) {
        pPkt = (pPkt+1)%MAXPKTNUM;

        pktLen = pktLenList[pPkt];
        dataLen = pktLen - 42;
        if (dataLen < 10) dataLen = 10;
        
        char srcIPStr[20] = {0};
        int randNumber = rand()%254 + 1;
        sprintf(srcIPStr, "10.0.0.%d", randNumber);

        //iphdr check
        ipHdr->tot_len = sizeof(struct iphdr) + sizeof(struct udphdr) + dataLen;
        ipHdr->check = 0;
        ipHdr->saddr = inet_addr(srcIPStr);
        ipHdr->daddr = inet_addr(dstIPStr);
        ipHdr->check = csum((uint16_t *) packet, (ipHdr->tot_len)/2); 
        //udphdr
        udpHdr->source = htons(srcPort);
        udpHdr->dest = htons(dstPort);
        udpHdr->len = htons(sizeof(struct udphdr) + dataLen);
        //pseudo packet
        pUDPPacket.srcAddr = inet_addr(srcIPStr);
        pUDPPacket.dstAddr = inet_addr(dstIPStr);
        pUDPPacket.UDP_len = htons(sizeof(struct udphdr) + dataLen);
        memset(pseudo_packet, 0, 1600);
        memcpy(pseudo_packet, (char *) &pUDPPacket, sizeof(struct pseudoUDPPacket));
        //udphdr check
        udpHdr->check = 0;
        memcpy(pseudo_packet + sizeof(struct pseudoUDPPacket), udpHdr, sizeof(struct udphdr));
        memset(pseudo_packet + sizeof(struct pseudoUDPPacket) + sizeof(struct udphdr), 0, dataLen);
        udpHdr->check = (csum((uint16_t *) pseudo_packet, ((int) (sizeof(struct pseudoUDPPacket) + 
              sizeof(struct udphdr) +  dataLen + 1))/2));

        //send packet
        int bytes = sendto(rawSock, packet, ipHdr->tot_len, 0, (struct sockaddr *) &addr_in, sizeof(addr_in));
        if(bytes < 0) {
            perror("Error on sendto()");
        }

        //sleep
        // for demRate = 0, not send pkt
        while(demRates[dstHostId] <= 0.01){
            usleep(5000);
        }
        int pktGap = 4000 / demRates[dstHostId];
        // TEST: sending speed
        usleep(pktGap);
    }
    pthread_exit(NULL);
}


void pthread_traffic() {
    int i = 0;
    int TMid = 0;
    printf("pthread_traffic()\n");
    for(i = 0; i < hostNum; i++) {
        demRates[i] = TMs[TMid+TMbegin][i];
    }

    while(sendFlag) {
        if (pktsenderPeriod == 0) {
            if(TMid+TMbegin >= TMend) break;
            for(i = 0; i < hostNum; i++) {
                demRates[i] = TMs[TMid+TMbegin][i];
            }
        } else {
            if(TMid >= pktsenderPeriod) break;
        }
        TMid++;
        sleep(5);
    }
    printf("pthread_traffic stop\n");
    sendFlag = false;
    pthread_exit(NULL);
}

/*main()*/
int main (int argc, char **argv) {
    hostId = atoi(argv[1]);
    hostNum = atoi(argv[2]);
    TMfile = argv[3];
    TMscale = atof(argv[4]);
    TMbegin = atoi(argv[5]);
    TMend = atoi(argv[6]);
    pktsenderPeriod = atoi(argv[7]); //failure flag
    printf("hostId:%d  hostNum:%d\nTMfile: %s \n", hostId, hostNum, TMfile);
    srand(time(NULL));

    // create raw socket
    int ret;
    addr_in.sin_family = AF_INET;
    addr_in.sin_port = htons(8000);
    char *remoteIPStr;
    sprintf(remoteIPStr, "10.0.0.%d", (hostId+1)%hostNum+1);
    addr_in.sin_addr.s_addr = inet_addr(remoteIPStr);
    int one = 1;
    if ((rawSock = socket(PF_INET, SOCK_RAW, IPPROTO_UDP)) < 0) {
        perror("Error while creating socket");
        exit(-1);
    }
    if (setsockopt(rawSock, IPPROTO_IP, IP_HDRINCL, (char *)&one, sizeof(one)) < 0) {
        perror("Error while setting socket options");
        exit(-1);
    }

    // prepare pkt length set
    rand_pkt_size();
    read_rate_file();
    // return 0;

    // open sender threads
    memset(thread, 0, sizeof(pthread_t)*MAXHOSTNUM);
    int i;
    for(i = 0; i < hostNum; i++) {
        if(i == hostId) continue;
        if((ret = pthread_create(thread+i*sizeof(pthread_t), NULL, (void*) pthread_sender, (void *)&i)) != 0)
            perror("Error while creating thread!\n");
        sleep(1);
    }

    sleep(5);
    sendFlag = true;

    pthread_t ptraffic;
    ret = pthread_create(&ptraffic, NULL, (void*) pthread_traffic, NULL);
    if (ret != 0) {
        perror("Error while creating thread!");
    }

    // when to stop
    while(sendFlag) {
        sleep(20);
    }
    sleep(5);
    free_all();
    return 0;
}
