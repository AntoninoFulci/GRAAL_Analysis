/* Fresh original-C oracle COMMON and deterministic integer rand stream only. */
#include "GRAAL_machine.h"
#include <stdio.h>
#include <stdlib.h>
#include "clus.h"
#include "pcn.h"
#include "angle.h"
#include "bgoprean.h"
__typeof__(clus_) clus_;
__typeof__(pcn_) pcn_;
__typeof__(angle_) angle_;
__typeof__(bgoprean_) bgoprean_;
static int random_values[480],random_count,random_used;
int oracle_rand(void){
  if(random_used>=random_count){fprintf(stderr,"oracle draw stream exhausted\n");exit(3);}
  return random_values[random_used++];
}
void count_cluster_ca_(int*,int[],int*);
int main(void){
  int cases,i,j,event,iclo,nero,iprog[480];
  if(scanf("%d%f%f",&cases,&pcn_.rcnt,&pcn_.tde)!=3)return 2;
  for(i=0;i<15;++i)if(scanf("%f",&angle_.tet[i])!=1)return 2;
  for(i=0;i<32;++i)if(scanf("%f",&angle_.phi[i])!=1)return 2;
  for(i=0;i<15;++i)if(scanf("%f",&angle_.vol[i])!=1)return 2;
  for(event=0;event<cases;++event){
    for(i=0;i<32;++i)for(j=0;j<15;++j)if(scanf("%f",&clus_.edepth[i][j])!=1)return 2;
    if(scanf("%d",&random_count)!=1 || random_count<0 || random_count>480)return 2;
    for(i=0;i<random_count;++i)if(scanf("%d",random_values+i)!=1)return 2;
    random_used=0;bgoprean_.nbclus=0;
    count_cluster_ca_(&iclo,iprog,&nero);
    printf("O %d %d %d %d\n",event,nero,random_used,iclo);
    for(i=0;i<iclo;++i){printf("C %d",iprog[i]);for(j=0;j<iprog[i];++j)printf(" %d",clus_.istack_p[j][i]);puts("");}
  }
  return 0;
}
