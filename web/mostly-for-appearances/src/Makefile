CLUSTER_NAME := mfa


cluster.kubeconfig:
	echo using infra kubeconfig...
	# # create cluster and expose ingress ports
	# k3d cluster list | grep -q "${CLUSTER_NAME}" || \
	# k3d cluster create "${CLUSTER_NAME}" \
	# 	--k3s-arg=--kubelet-arg=feature-gates=KubeletInUserNamespace=true@server:* \
	# 	-p "8000:80@loadbalancer" -p "8443:443@loadbalancer" \
	# 	-p "00:80@loadbalancer" -p "443:443@loadbalancer"
	# k3d kubeconfig merge "${CLUSTER_NAME}" --output cluster.kubeconfig

bootstrap: cluster.kubeconfig
	tofu -chdir=tofu-setup init
	tofu -chdir=tofu-setup plan -out tofu.tfplan -target helm_release.authentik

plan: cluster.kubeconfig
	tofu -chdir=tofu-setup init
	tofu -chdir=tofu-setup plan -out tofu.tfplan $(ARGS)

apply: cluster.kubeconfig
	tofu -chdir=tofu-setup apply tofu.tfplan

destroy:
	tofu -chdir=tofu-setup destroy

down: destroy
	rm cluster.kubeconfig
	k3d cluster delete "${CLUSTER_NAME}"


REGISTRY ?= registry.digitalocean.com/ctf-mfa-testing
images: \
	$(REGISTRY)/web-mfa\:apache \
	$(REGISTRY)/web-mfa\:voip-manager \
	$(REGISTRY)/web-mfa\:instance-manager \
	$(REGISTRY)/web-mfa\:phone-asterisk \
	$(REGISTRY)/web-mfa\:phone-call-triggerer \
	$(REGISTRY)/web-mfa\:phone-employee-answerer \
	$(REGISTRY)/web-mfa\:phone-ui \
	$(REGISTRY)/web-mfa\:flag-email \

$(REGISTRY)/web-mfa\:apache:
	docker build -t $@ ./apache
	#docker push $@
$(REGISTRY)/web-mfa\:voip-manager:
	docker build -t $@ ./voip-manager
	#docker push $@

$(REGISTRY)/web-mfa\:instance-manager:
	docker build -t $@ ./instance-manager
	#docker push $@

$(REGISTRY)/web-mfa\:phone-asterisk:
	docker build -t $@ ./phone-instance/asterisk
	#docker push $@
$(REGISTRY)/web-mfa\:phone-call-triggerer:
	docker build -t $@ ./phone-instance/call-triggerer
	#docker push $@
$(REGISTRY)/web-mfa\:phone-employee-answerer:
	docker build -t $@ ./phone-instance/employee-answerer
	#docker push $@
$(REGISTRY)/web-mfa\:phone-ui:
	docker build -t $@ ./phone-instance/voip-phone-ui
	#docker push $@

$(REGISTRY)/web-mfa\:flag-email:
	docker build -t $@ ./flag-email
	#docker push $@
