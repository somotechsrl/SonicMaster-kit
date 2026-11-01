/* Read-only JACK meter/capture; optional isolated test tone output. */
#include <math.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
typedef void jack_client_t;typedef void jack_port_t;typedef unsigned int frames_t;
extern jack_client_t *jack_client_open(const char*,unsigned int,unsigned int*,...);
extern int jack_client_close(jack_client_t*);extern int jack_activate(jack_client_t*);extern int jack_deactivate(jack_client_t*);
extern frames_t jack_get_sample_rate(jack_client_t*);extern const char *jack_get_client_name(jack_client_t*);
extern int jack_set_process_callback(jack_client_t*,int(*)(frames_t,void*),void*);
extern jack_port_t *jack_port_register(jack_client_t*,const char*,const char*,unsigned long,unsigned long);
extern void *jack_port_get_buffer(jack_port_t*,frames_t);extern int jack_connect(jack_client_t*,const char*,const char*);
static jack_port_t *inputs[8],*outputs[2];static int count,tone;static unsigned rate;static unsigned long long frame;
static _Atomic float peaks[8];static float *recorded;static size_t written,capacity;
static int process(frames_t n,void *unused){
 (void)unused;
 if(tone){float *a=jack_port_get_buffer(outputs[0],n),*b=jack_port_get_buffer(outputs[1],n);for(unsigned i=0;i<n;i++){float v=.02f*sinf((float)(2.*3.141592653589793*440.*(frame+i)/rate));a[i]=v;b[i]=v;}frame+=n;}
 for(int p=0;p<count;p++){
  float *b=jack_port_get_buffer(inputs[p],n);float peak=0;
  for(unsigned i=0;i<n;i++)if(fabsf(b[i])>peak)peak=fabsf(b[i]);
  if(peak>atomic_load(&peaks[p]))atomic_store(&peaks[p],peak);
  if(p==0&&recorded&&written+n<=capacity){memcpy(recorded+written,b,n*sizeof(float));written+=n;}
 }
 return 0;
}
int main(int argc,char **argv){
 if(argc<4)return 2;
 float seconds=strtof(argv[1],0);const char *file=argv[2];int first=3;
 if(!strcmp(argv[first],"--tone")){tone=1;first++;}
 count=argc-first;if(count>8)return 2;
 unsigned status=0;jack_client_t *c=jack_client_open("TSMA_Probe",1,&status);if(!c)return 3;
 rate=jack_get_sample_rate(c);capacity=(size_t)(seconds*rate)+rate;
 if(strcmp(file,"-"))recorded=calloc(capacity,sizeof(float));
 for(int i=0;i<count;i++){char name[32];snprintf(name,sizeof(name),"in_%d",i+1);inputs[i]=jack_port_register(c,name,"32 bit float mono audio",1,0);}
 if(tone)for(int i=0;i<2;i++){char name[32];snprintf(name,sizeof(name),"out_%d",i+1);outputs[i]=jack_port_register(c,name,"32 bit float mono audio",2,0);}
 jack_set_process_callback(c,process,0);jack_activate(c);
 for(int i=0;i<count;i++){char dest[128];snprintf(dest,sizeof(dest),"%s:in_%d",jack_get_client_name(c),i+1);if(jack_connect(c,argv[first+i],dest))fprintf(stderr,"Cannot tap %s\n",argv[first+i]);}
 printf("READY %s %u\n",jack_get_client_name(c),rate);fflush(stdout);
 for(int tick=0;tick<(int)(seconds*4);tick++){usleep(250000);printf("PEAK");for(int i=0;i<count;i++){float p=atomic_exchange(&peaks[i],0);printf(" %s=%.1fdB",argv[first+i],p>0?20*log10f(p):-200.);}puts("");fflush(stdout);}
 jack_deactivate(c);jack_client_close(c);
 if(recorded){FILE *f=fopen(file,"wb");if(!f)return 4;fwrite(recorded,sizeof(float),written,f);fclose(f);free(recorded);}
 return 0;
}
