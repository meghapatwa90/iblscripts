cd /home/ibladmin/Documents/PYTHON/iblscripts/deploy/serverpc/kilosort2
rootH = '/mnt/s';

ROOTZ = {...
   '/mnt/s0/Data/Subjects/cer-5/2019-10-24/001/raw_ephys_data/probe00',...
'/mnt/s0/Data/Subjects/cer-5/2019-10-24/001/raw_ephys_data/probe01',...
'/mnt/s0/Data/Subjects/cer-5/2019-10-23/001/raw_ephys_data/probe00',...
'/mnt/s0/Data/Subjects/cer-5/2019-10-23/001/raw_ephys_data/probe01',...
'/mnt/s0/Data/Subjects/cer-5/2019-10-25/001/raw_ephys_data/probe00',...
'/mnt/s0/Data/Subjects/cer-5/2019-10-25/001/raw_ephys_data/probe01',...
};


for m= 1:length(ROOTZ)
    rootZ = ROOTZ{m};
    disp(rootZ)
    run_ks2_ibl(rootZ, rootH)
end
