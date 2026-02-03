      SUBROUTINE UMAT(STRESS,STATEV,DDSDDE,SSE,SPD,SCD,
     1 RPL,DDSDDT,DRPLDE,DRPLDT,
     2 STRAN,DSTRAN,TIME,DTIME,TEMP,DTEMP,PREDEF,DPRED,CMNAME,
     3 NDI,NSHR,NTENS,NSTATV,PROPS,NPROPS,COORDS,DROT,PNEWDT,
     4 CELENT,DFGRD0,DFGRD1,NOEL,NPT,LAYER,KSPT,JSTEP,KINC)
C
      INCLUDE 'ABA_PARAM.INC'
C
      CHARACTER*80 CMNAME
      DIMENSION STRESS(NTENS),STATEV(NSTATV),
     1 DDSDDE(NTENS,NTENS),DDSDDT(NTENS),DRPLDE(NTENS),
     2 STRAN(NTENS),DSTRAN(NTENS),TIME(2),PREDEF(1),DPRED(1),
     3 PROPS(NPROPS),COORDS(3),DROT(3,3),DFGRD0(3,3),DFGRD1(3,3),
     4 JSTEP(4)
c
      integer i,j,k,ip,ip2,fakn,info
c 材料参数申明
      double precision P_E,P_Nu,Shear_modulus,P_SigmaY0,P_Xi(2),P_Gamma(2),P_m,P_Tau0,P_K,P_n,
     1 P_Lambda,P_Delta,P_Phi,P_Omega,P_b,P_Qsa,P_H
c 状态变量申明
      double precision pacc,snp(6),bhi(2,6),qiso,qm
c 中间变量申明
      double precision tvs(6),em(6,6),vem(6,6),alpha(6),xx,fy,
     1 odp,thi(2),dp,dsnp(6),tbhi(6,6),yaa,tau,yst
      double precision tah(6),tsef,tvsa(6),x0,fy0,ttsef,hh,
     1 y0,y1,x1,vsa(6),vsef,dqiso
      double precision xx_alpa(2),bbar(2),vmu
      double precision xakn(3)
      double precision vmj1(6,6),xx1,vmj2(6,6),vmjiv1(6,6),
     1 vmjiv2(6,6),aa1(2),hkm1(6,6),hkm2(6,6),hkm(6,6)
      double precision bh2(2,6),vmup,taup,xx2,bh1(6),vsef1,
     1 pm1(6,6),pnn(6),pn1(6),pn0(6),clit2,clit0,fy1,aa0,aa2,
     2 pm(6,6)
      double precision vlm(6,6),vlminv(6,6),ym1(6,6),xm(6,6),
     1 xm1(6,6)
c 材料参数赋值
      P_E=props(1)                          !弹性模量
      P_Nu=props(2)                         !泊松比
      Shear_modulus=0.5d0*P_E/(1.0d0+P_Nu)  !剪切模量
      P_SigmaY0=props(3)                    !初始屈服应力
      P_Xi(1)=props(4)                      !ξ1
      P_Xi(2)=props(5)                      !ξ2
      P_Gamma(1)=props(6)                   !γ1
      P_Gamma(2)=props(7)                   !γ2
      P_m=props(8)                          !m
      P_Tau0=props(9)                       !τ0
      P_K=props(10)                         !K
      P_n=props(11)                         !n
      P_Lambda=props(12)                    !λ
      P_Delta=props(13)                     !δ
      P_Phi=props(14)                       !Φ
      P_Omega=props(15)                     !ω
      P_b=props(16)                         !b
      P_Qsa=props(17)                       !Qsa
      P_H=props(18)                         !H
c 状态变量赋值
      k=1
      pacc=statev(k)                        !累计塑性应变SDV1
      k=k+1
      do j=1,6
        snp(j)=statev(k)                    !塑性应变张量SDV2-SDV7
        k=k+1
      end do
      do i=1,2
        do j=1,6 
            bhi(i,j)=statev(k)              !背应力张量分量：背应力1SDV8-SDV13；背应力1SDV14-SDV19
            k=k+1
		end do
	  end do
      qiso=statev(k)                        !各向同性硬化应力SDV20
      qm=qiso
c Elastic stiffness
      call kmkem(em, Shear_modulus, P_Nu)
      call kmkvem(Shear_modulus, vem)
c 计算偏试应力
      do i=1,6
        tvs(i)=0.0d0
        do j=1,6
            tvs(i)=tvs(i)+vem(i,j)*(stran(j)+dstran(j)-snp(j))
		end do
      end do
c 计算总背应力 alpha = sum_i b_i
      do j=1,6
          alpha(j)=0.0d0
          do i=1,2
              alpha(j)=alpha(j)+bhi(i,j)
		  end do
      end do
c 计算屈服函数
      xx=0.0d0
      do j=1,3
          xx=xx+(tvs(j)-alpha(j))**2
	  end do
      do j=4,6,1
          xx=xx+2.0d0*(tvs(j)-alpha(j))**2
      end do
c
      fy=sqrt(1.5d0*xx)-(qiso+P_SigmaY0)
      if (fy < 1.0d-10*max(P_SigmaY0,1.0d0)) fy = 0.0d0
c 判断是否屈服
      if (fy .gt. 0.0d0) then
c 牛顿迭代
          ip=1
          fakn=0
          odp=0.0d0
          do i=1,2
              thi(i)=1.0d0
          end do
c ____________________________________________________________________________________________________________
10        do j=1, 6
              tah(j)=0.0d0
              do i=1, 2
                  tah(j)=tah(j)+thi(i)*bhi(i,j)
              end do
          end do
c
          tsef=0.0d0
          do j=1,3
              tvsa(j)=tvs(j)-tah(j)                   !试偏应力-试背应力
              tsef=tsef+tvsa(j)**2
          end do
          do j=4,6,1
              tvsa(j)=tvs(j)-tah(j)
              tsef=tsef+2.0d0*tvsa(j)**2
          end do
          tsef=sqrt(1.5d0*tsef)                       !对应 Y*拔，试等效偏量
c
          x0=tsef
          ip2=1
110       fy0=(x0-(qiso+P_SigmaY0))/P_K               !流动率括号内的整体，表明试屈服函数的正负性
c
          if (fy0 .le. 0.0d0) then
              ttsef=tsef                              !（Y拔=Y*拔）
              dp=0.0d0
              goto 100
          else
          end if
c 试屈服函数>0，进行塑性修正
          hh=0.0d0
          do i=1,2
              hh=hh+thi(i)*P_Gamma(i)*P_Xi(i)
          end do
          y0=x0+(3.0d0*Shear_modulus+hh)*dtime*(fy0)**P_n-tsef
          y1=1.0d0+P_n*(fy0)**(P_n-1.0d0)*(dtime/P_K)*(3.0d0*Shear_modulus+hh)
c
          if (y1.eq.0.0d0)then
              print *, 'It is failed in convergent process,
     1 please decrease the time-step'
              goto 100
          end if
c
          x1=x0-(y0/y1)
          if ((abs((x1-x0)/x0) .gt. 1.0d-8) .and. (ip2 .lt.200)) then
              x0=x1
              ip2=ip2+1
              goto 110
          else
              ttsef=x1                                !ttsef: [sqrt(1.5d0)*(最终确定的||偏应力-背应力||)]
          end if
c
          dp=dtime*((ttsef-(qiso+P_SigmaY0))/P_K)**P_n
100	    do j=1,6
              vsa(j)=tvsa(j)*ttsef/(ttsef+(3.0d0*Shear_modulus+hh)*dp)  !最终确定的（偏应力-背应力）
              dsnp(j)=1.5d0*dp*vsa(j)/ttsef
          end do
c
          vsef=ttsef                                  !sqrt(1.5d0)*(最终确定的||偏应力-背应力||)
c ____________________________________________________________________________________________________________
c 加速算法求塑性应变增量
          xakn(1)=xakn(2)
          xakn(2)=xakn(3)
          xakn(3)=dp
          if (fakn .ne. 3) then
              fakn=fakn+1
          elseif (abs( xakn(3)-xakn(2) ) .gt. 1.0d-10*dp) then
              dp=xakn(3)-(xakn(3)-xakn(2))
     1 /(1.0d0-(xakn(2)-xakn(1))/(xakn(3)-xakn(2)))
          if (dp .lt. 0.0d0) then
              dp=xakn(3)
          else
              do j=1,ntens
                  dsnp(j)=dsnp(j)*dp/xakn(3)
              end do
              xakn(3)=dp
              fakn=2
          endif
          endif
c ____________________________________________________________________________________________________________
c 计算后继屈服应力
          qiso=(1.0d0/(1.0d0+P_b*dp))*(qm+P_b*P_Qsa*dp+P_H*(1.0d0+P_b*pacc)*dp)
c ____________________________________________________________________________________________________________
          do i=1,2
              xx_alpa(i)=0.0d0
              do j=1,3
                  xx_alpa(i)=xx_alpa(i)+bhi(i,j)**2
		    end do
              do j=4,6,1
                  xx_alpa(i)=xx_alpa(i)+2.0d0*bhi(i,j)**2
		    end do  
              xx_alpa(i)=sqrt(1.5d0*xx_alpa(i))
          end do
c
          do i=1,2
              bbar(i)=0.0d0
              do j=1,3
                  tbhi(i,j)=bhi(i,j)+P_Xi(i)*P_Gamma(i)*dsnp(j)/1.5d0       !b*
                  bbar(i)=bbar(i)+tbhi(i,j)**2                              !b*拔
		    end do
              do j=4,6,1
                  tbhi(i,j)=bhi(i,j)+P_Xi(i)*P_Gamma(i)*dsnp(j)/1.5d0
                  bbar(i)=bbar(i)+2.0d0*tbhi(i,j)**2
		    end do
              bbar(i)=sqrt(1.5d0*bbar(i))
          end do
c背应力1：保持原来的线性缩放
          thi(1)=1.0d0/(1.0d0+P_Xi(1)*dp)
c背应力2：用旧背应力线性2缩放
          vmu=1.0d0+P_Lambda*(1.0d0-exp(-P_Delta*(pacc+dp)))
          tau=P_Tau0*(P_Phi+(1.0d0-P_Phi)*exp(-P_Omega*(pacc+dp)))
          thi(2)=1.0d0/(1.0d0+vmu*P_Xi(2)*dp+tau*xx_alpa(2)**(P_m-1)*dtime)
c
c 可选背应力2：“共线 + 标量牛顿”更新
c r2 = tbhi(2,*) = bhi(2,*) + Xi2*Gamma2*dsnp/1.5
c      r2eq = sqrt( 1.5d0*( tbhi(2,1)**2 + tbhi(2,2)**2 + tbhi(2,3)**2
c          &              + 2.0d0*( tbhi(2,4)**2 + tbhi(2,5)**2 + tbhi(2,6)**2 ) ) )
c      vmu  = 1.0d0 + P_Lambda*(1.0d0 - exp(-P_Delta*(pacc+dp)))
c      tau  = P_Tau0*( P_Phi + (1.0d0-P_Phi)*exp(-P_Omega*(pacc+dp)) )
c      k1 = P_Xi(2)*vmu*dp
c      k2 = tau*DTIME
c          if (r2eq .le. 1.0d-30) then
c             thi(2) = 0.0d0
c          else
c             anorm = r2eq/(1.0d0 + k1)
c             converged = .false.
c             it = 1
c 800         continue
c             f  = (1.0d0+k1)*anorm + k2*anorm**P_m - r2eq
c             df = (1.0d0+k1) + k2*P_m*(DMAX1(anorm,1.0d-30))**(P_m-1.0d0)
c             anew = anorm - f/df
c             if ( DABS(anew-anorm) .le.
c     1            (1.0d-10 + 1.0d-8*DMAX1(1.0d0,anorm)) ) then
c                converged = .true.
c                goto 900
c             end if
c             anorm = anew
c             if (anorm .lt. 0.0d0) anorm = 0.0d0
c             it = it + 1
c             if (it .le. 30) goto 800
c 900         continue
c             thi(2) = anorm / r2eq
c          end if
c ____________________________________________________________________________________________________________
          if ((abs(dp-odp).gt.1.0d-5*dp).and.(ip.lt.25))then
              ip=ip+1
              odp=dp
              goto 10
          else
          endif
c ____________________________________________________________________________________________________________
c 更新变量
          pacc=pacc+dp       
          do j=1,6
              snp(j)=snp(j)+dsnp(j)
          end do
		  do j=1,6
			alpha(j)=0.0d0
			do i=1,2
                  bhi(i,j)=thi(i)*tbhi(i,j)
				alpha(j)=alpha(j)+bhi(i,j)
			end do
          end do
          yaa = sqrt( 1.5d0 * ( alpha(1)**2 + alpha(2)**2 + alpha(3)**2
     1       + 2.0d0*( alpha(4)**2 + alpha(5)**2 + alpha(6)**2 ) ) )
          tau=P_Tau0*(P_Phi+(1-P_Phi)*exp(-P_Omega*pacc))
          yst=tau*yaa**(P_m-1)*dtime
      endif
c 更新应力
      do i=1,6
          stress(i)=0.0d0
          do j=1,6
              stress(i)=stress(i)+
     1 em(i,j)*(stran(j)+dstran(j)-snp(j))
		end do
      end do
c ____________________________________________________________________________________________________________
c切线刚度矩阵
      if (fy .gt. 0.0d0) then
          vmj1 = 0.0d0
          do i = 1, 6
              vmj1(i,i) = 1.0d0
          end do 
c
          do i=1,2
              xx_alpa(i)=0.0d0
              do j=1,3
                  xx_alpa(i)=xx_alpa(i)+bhi(i,j)**2
		    end do
              do j=4,6,1
                  xx_alpa(i)=xx_alpa(i)+2.0d0*bhi(i,j)**2
		    end do  
              xx_alpa(i)=sqrt(1.5d0*xx_alpa(i))
          end do
          tau=P_Tau0*(P_Phi+(1.0d0-P_Phi)*exp(-P_Omega*pacc))
          xx1=1.5d0*thi(2)*tau*(P_m-1.0d0)*xx_alpa(2)**(P_m-3.0d0)*dtime
c
          do j=1,6
              do k=1,3
                  vmj2(j,k)=xx1*bhi(2,j)*bhi(2,k)     !两个行列式求双张量积
		    end do
              do k=4,6,1
                  vmj2(j,k)=2.0d0*xx1*bhi(2,j)*bhi(2,k)     !两个行列式求双张量积
              end do
              vmj2(j,j)=1.0d0+vmj2(j,j)
          end do
c
          call kminv(vmj1,vmjiv1,info)
          call kminv(vmj2,vmjiv2,info)
c
          do i=1,2
              aa1(i)=thi(i)*P_Xi(i)*P_Gamma(i)/1.5d0
          end do
c
c
          do j=1,6
              do k=1,3
                  hkm1(j,k)=aa1(1)*vmjiv1(j,k)
              end do
              do k=4,6,1
                  hkm1(j,k)=2.0d0*aa1(1)*vmjiv1(j,k)
              end do
          end do
c
c
          do j=1,6
              do k=1,6
                  hkm2(j,k)=aa1(2)*vmjiv2(j,k)
              end do
              do k=4,6,1
                  hkm2(j,k)=2.0d0*aa1(2)*vmjiv2(j,k)
              end do
          end do
c
          hkm=hkm1+hkm2
c ____________________________________________________________________________________________________________
          do j=1,6                                        !计算b'
              bh2(1,j)=0.0d0
              bh2(2,j)=0.0d0
              do k=1,3
                  bh2(1,j)=bh2(1,j) + vmjiv1(j,k) * bhi(1,k)
                  bh2(2,j)=bh2(2,j) + vmjiv2(j,k) * bhi(2,k)
              end do
              do k=4,6
                  bh2(1,j)=bh2(1,j) +  vmjiv1(j,k) * bhi(1,k)
                  bh2(2,j)=bh2(2,j) +  vmjiv2(j,k) * bhi(2,k)
              end do
          end do
c
          vmu=1.0d0+P_Lambda*(1.0d0-exp(-P_Delta*pacc))
          vmup=-P_Lambda*P_Delta*exp(-P_Delta*pacc)
          tau=P_Tau0*(P_Phi+(1.0d0-P_Phi)*exp(-P_Omega*pacc))
          taup=P_Tau0*(-P_Omega)*(1-P_Phi)*exp(-P_Omega*pacc)
          xx2=P_Xi(2)*vmup*dp+P_Xi(2)*vmu+taup*xx_alpa(2)**(P_m-1.0d0)*dtime
c
          do j=1,6
              bh1(j)=-thi(1)*P_Xi(1)*bh2(1,j)
     1 -thi(2)*xx2*bh2(2,j)
          end do
c
          vsef1=sqrt(1.50d0)/vsef                           !计算J
          do j=1,6
              do k=1,6
                  pm1(j,k)=0.0d0
		    end do
              pnn(j)=sqrt(1.5d0)*tvsa(j)/tsef
              pm1(j,j)=vsef1
          end do
          do j=1,6
              do k=1,3
                  pm1(j,k)=pm1(j,k)-vsef1*pnn(j)*pnn(k)
		    end do
              do k=4,6,1
                  pm1(j,k)=pm1(j,k)-2.0d0*vsef1*pnn(j)*pnn(k)
		    end do
          end do
c
          do j=1,6                                          !计算n0
              pn1(j)=0.0d0
              do k=1,3
                  pn1(j)=pn1(j)+dp*pm1(j,k)*bh1(k)
		    end do
              do k=4,6,1
                  pn1(j)=pn1(j)+2.0d0*dp*pm1(j,k)*bh1(k)
		    end do
              pn0(j)=pnn(j)-pn1(j)
          end do
c
          clit2=0.0d0                                       !计算系数A
          do i=1,3
              clit2=clit2+sqrt(1.5d0)*pnn(i)*bh1(i)+P_b*(P_Qsa-qm)
	    end do
          do i=4,6,1
              clit2=clit2+2.0d0*sqrt(1.5d0)*pnn(i)*bh1(i)+P_b*(P_Qsa-qm)
          end do
          clit0=clit2
          fy1=vsef-qiso-P_SigmaY0
          if (fy1 .le. 0.0d0) then
              fy1=0.0d0
          else
          endif          
          aa0=(P_n*dtime/P_K)*((fy1/P_K)**(P_n-1.0d0))
          aa2=aa0/(1.0d0+aa0*clit0)
c
          do j=1,6                                           !计算J0
              do k=1,6
                  pm(j,k)=sqrt(1.5d0)*dp*pm1(j,k)
		    end do
	    end do
          do j=1,6
              do k=1,3
                  pm(j,k)=pm(j,k)+1.5d0*aa2*pnn(j)*pn0(k)
		    end do
              do k=4,6,1
                  pm(j,k)=pm(j,k)+2.0d0*1.5d0*aa2*pnn(j)*pn0(k)
		    end do
      end do
c ____________________________________________________________________________________________________________
c
          do j=1,6
              hkm(j,j)=hkm(j,j)+2.0d0*Shear_modulus
          end do
c vlm = pm @ hkm
          do i = 1, 6
          do j = 1, 6
              vlm(i,j) = 0.0d0
              do k = 1, 6
              vlm(i,j) = vlm(i,j) + pm(i,k) * hkm(k,j)
              end do
          end do
          end do

c L = I + pm@hkm
          do i = 1, 6
          vlm(i,i) = vlm(i,i) + 1.0d0
          end do
          call kminv(vlm,vlminv,info)                       !计算L矩阵及其逆矩阵
          call kmprod(vlminv,pm,ym1)                        !形成DDSDDE
          call kmprod(ym1,vem,xm)
          call kmprod(em,xm,xm1)
          do j=1,6
              do k=1,6
                  em(j,k)=em(j,k)-xm1(j,k)
		    end do
          end do      
      endif
c
      do i=1,6
          do j=1,6
              ddsdde(i,j)=em(i,j)
		end do
      end do
c ____________________________________________________________________________________________________________
c 更新状态变量
      k=1
      statev(k)=pacc
      k=k+1
      do j=1,6
          statev(k)=snp(j)
          k=k+1
	end do
      do i=1,2
          do j=1,6
              statev(k)=bhi(i,j)
              k=k+1
		end do
      end do
      statev(k)=qiso
c
      return
      end
c ____________________________________________________________________________________________________________
      subroutine kmkem(em, Shear_modulus, P_Nu)
      implicit none
      double precision, intent(in)  :: Shear_modulus, P_Nu
      double precision, intent(out) :: em(6,6)
      double precision :: G, lam, one_minus_2nu
      integer :: i, j
c
      G = Shear_modulus
      one_minus_2nu = 1.0d0 - 2.0d0*P_Nu
      lam = 2.0d0*G*P_Nu / one_minus_2nu
c清零
      do i = 1,6
         do j = 1,6
            em(i,j) = 0.0d0
         end do
      end do
c正应力-应变块
      do i = 1,3
         em(i,i) = lam + 2.0d0*G
      end do
      do i = 1,3
         do j = 1,3
            if (i .ne. j) em(i,j) = lam
         end do
      end do
c剪切刚度（工程剪应变）
      em(4,4) = G
      em(5,5) = G
      em(6,6) = G
      end subroutine kmkem
c ____________________________________________________________________________________________________________
      subroutine kmkvem(Shear_modulus, vem)                     !偏弹性算子（deviatoric elastic operator）
      implicit none
      double precision, intent(in)  :: Shear_modulus            !G
      double precision, intent(out) :: vem(6,6)
      double precision :: G, twoG_over_3
      integer :: i, j
c
      G = Shear_modulus
      twoG_over_3 = (2.0d0/3.0d0)*G
c清零
      do i = 1,6
        do j = 1,6
          vem(i,j) = 0.0d0
        end do
      end do
c正应变块: diag = 4G/3, offdiag = -2G/3
      do i = 1,3
        do j = 1,3
          if (i == j) then
            vem(i,j) = 2.0d0*G - twoG_over_3                    ! = 4G/3
          else
            vem(i,j) = -twoG_over_3
          end if
        end do
      end do
c剪切：工程剪应变下 τ = G * γ
      vem(4,4) = G
      vem(5,5) = G
      vem(6,6) = G
      end subroutine kmkvem
c ____________________________________________________________________________________________________________
      subroutine kmlu6(A, LU, ipiv, info)
c----- LU factorization with partial pivoting for 6x6
      implicit none
      double precision A(6,6), LU(6,6), tmp, pivmax
      integer ipiv(6), info, i, j, k, p, r
c copy
      do i=1,6
        do j=1,6
          LU(i,j) = A(i,j)
        end do
        ipiv(i) = i
      end do
      info = 0
c loop over columns
      do k=1,6
c find pivot
        pivmax = 0d0
        p = k
        do r=k,6
          if (abs(LU(r,k)) .gt. pivmax) then
            pivmax = abs(LU(r,k))
            p = r
          end if
        end do
        if (pivmax .le. 1d-30) then
          info = k
          return
        end if
c row swap
        if (p .ne. k) then
          do j=1,6
            tmp      = LU(k,j)
            LU(k,j)  = LU(p,j)
            LU(p,j)  = tmp
          end do
          i       = ipiv(k)
          ipiv(k) = ipiv(p)
          ipiv(p) = i
        end if
c eliminate below
        if (k .lt. 6) then
          do i=k+1,6
            LU(i,k) = LU(i,k)/LU(k,k)
            do j=k+1,6
              LU(i,j) = LU(i,j) - LU(i,k)*LU(k,j)
            end do
          end do
        end if
      end do
      end subroutine kmlu6

      subroutine kmlusolve6(LU, ipiv, B, X)
c solve A X = B given LU and ipiv
      implicit none
      double precision LU(6,6), B(6,6), X(6,6)
      double precision Y(6,6)
      integer ipiv(6), i, j, k, nrhs

c assume up to 6 RHS; if fewer, just fill B other cols with zeros
      nrhs = 6

c apply row pivots to B: Y = P*B
      do k=1,nrhs
        do i=1,6
          Y(i,k) = B(ipiv(i),k)
        end do
      end do

c forward solve: L*Y = P*B (Y is overwritten in-place above)
      do k=1,nrhs
        do i=2,6
          do j=1,i-1
            Y(i,k) = Y(i,k) - LU(i,j)*Y(j,k)
          end do
        end do
      end do

c back solve: U*X = Y
      do k=1,nrhs
        do i=6,1,-1
          do j=i+1,6
            Y(i,k) = Y(i,k) - LU(i,j)*X(j,k)
          end do
          X(i,k) = Y(i,k)/LU(i,i)
        end do
      end do
      end subroutine kmlusolve6

      subroutine kminv(A, Ainv, info)
c compute inverse via LU + solves: Ainv = A^{-1}
      implicit none
      double precision A(6,6), Ainv(6,6), I6(6,6), LU(6,6)
      integer ipiv(6), info, i, j

c identity
      do i=1,6
        do j=1,6
          I6(i,j) = 0d0
        end do
        I6(i,i) = 1d0
      end do

c factor
      call kmlu6(A, LU, ipiv, info)
      if (info .ne. 0) return

c solve A * Ainv = I
      call kmlusolve6(LU, ipiv, I6, Ainv)
      end subroutine kminv
c ____________________________________________________________________________________________________________
      subroutine kmprod( am,bm,cm )
      include 'aba_param.inc'
      double precision am(6,6),bm(6,6),cm(6,6)
      integer i,j,k
      do j=1,6
          do k=1,6
              cm(j,k)=0.0d0
              do i=1,6
                  cm(j,k)=cm(j,k)+am(j,i)*bm(i,k)
			end do
		end do
	  end do
c
      return
      end