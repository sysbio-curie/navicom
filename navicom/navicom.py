################################################################################
# navicom.py
# By Mathurin Dorel
# Import data from a file and create analyzed sets to export to NaviCell
################################################################################

from curie.navicell import *
from .navidata import *
from .displayConfig import *

DEBUG_NAVICOM = False
VERBOSE_NAVICOM = True


def getLine(ll, split_char="\t"):
    ll = re.sub('\"', '', ll.strip())
    ll = re.sub('\tNA', '\tNaN', ll) # Python float can convert "NaN" -> nan but not "NA" -> nan
    ll = re.sub('\tnull', '\tNaN', ll) # Same for null
    ll = ll.split(split_char)
    for ii in range(len(ll)):
        try:
            ll[ii] = float(ll[ii])
        except:
            pass
    return(ll)

# Aliases by biotype
MRNA_ALIASES = ["MRNA", "RNA"]
DNA_ALIASES = ["CNV", "CNA", "CCNA", "CCNV", "DNA"]
PROTEIN_ALIASES = ["PROTEINS", "PROTEOMICS", "PROTEIN"]
METHYLATION_ALIASES = ["HISTONE", "HISTONES", "METHYLATION"]
# Complete list of aliases
BIOTYPES_ALIASES = {"mRNA":MRNA_ALIASES, "dna":DNA_ALIASES, "proteins":PROTEIN_ALIASES, "methylation":METHYLATION_ALIASES}
ALL_ALIASES = []
for aliases in BIOTYPES_ALIASES.values():
    ALL_ALIASES += aliases

class NaviCom():
    """
    NaviComm class to handle data and display them in a standardized way on NaviCell maps
    """

    def __init__(self, map_url='https://navicell.curie.fr/navicell/maps/cellcycle/master/index.php', fname="", modules_dict="", browser_command="firefox %s", display_config=DisplayConfig(), name="no name"):
        """
        Initialize a Navicell communication object.
        Args:
            map_url (str): URL of the NaviCell map
            fname (str): name of the data file to load
            modules_dict (str): name of the module definition file (.gmt) to load
            browser_command (str): command to open the browser
        """
        # Name of the dataset
        self.name = name
        # Representation of the data
        self._display_config = display_config
        # Data, indexed by processing then type of data
        self._processings = PROCESSINGS
        self._data = dict() # All data
        self._exported_data = dict() # Whether data have been exported yet
        self._data_names = dict() # Name of the exported data
        self._associated_data = dict() # Processing and method associated to each name
        for processing in self._processings:
            self._data[processing] = dict()
            self._exported_data[processing] = dict()
            self._data_names[processing] = dict()
        self._exported_data["uniform"] = False
        ## Annotations of the samples
        self._annotations = dict()
        ## Composition of the modules
        self.modules = dict()
        self._associated_modules = dict() # Number of modules each gene belong to
        if (fname != ""):
            self.loadData(fname)
            self.defineModules(modules_dict)
        # NaviCell connexion
        self._map_url = None
        self._browser_command = None
        self.newNaviCell(map_url, browser_command)
        # Remember how many samples and datatables were selected in NaviCell in the heatmap and barplot editors
        self._hsid = 0
        self._hdid = 0
        self._bid = 0
        # List of genes from the NaviCell map
        self._map_hugos = list()
        self._uptodate_hugos = False

    def listData(self):
        print("Data available :")
        for processing in self._processings:
            for dname in self._data[processing]:
                if (dname.lower() in METHODS_TYPE):
                    print("\t" + processing + " " + dname + ": " + METHODS_TYPE[dname.lower()] + " (biotype: " + TYPES_BIOTYPE[METHODS_TYPE[dname.lower()]] + ")")
                else:
                    print("\t" + processing + " " + dname)

    def listAnnotations(self):
        print("Annotations available (values) :")
        for annot in self._annotations._annotations:
            print("\t" + annot + " : " + str(set(self._annotations[annot])))

    def __repr__(self):
        rpr = "NaviCom object with " + str(len(self._data)) + " types of data:\n"
        for method in self._data:
            rpr += method + ": " + str(self._data[method]) + "\n"
        rpr += "and " + str(len(self.moduleAverage)) + " modules average:\n"
        for method in self.moduleAverage:
            rpr += method + ": " + str(self.moduleAverage[method]) + "\n"
        return(repr)
    
    def _nameData(self, method, processing="raw", name=""):
        if (name == ""):
            name = method + "_" + processing
        self._data_names[processing][method] = name
        self._associated_data[name] = (processing, method)
        return (name)

    def getDataName(self, data_name):
        """
        Return the string identifier corresponding to the data name or tuple

        Args:
            data_name (str or tuple): Identifier of the data
        """
        dTuple = self.getDataTuple(data_name)
        if (dTuple[0] == 'uniform'):
            return('uniform')
        return(self._data_names[dTuple[0]][dTuple[1]])

    def getDataTuple(self, data_name):
        """
        Return tuple corresponding to the data name or tuple
        """
        if (isinstance(data_name, str)):
            if (data_name == 'uniform'):
                return(('uniform', 'uniform'))
            elif (data_name in self._associated_data):
                return(self._associated_data[data_name])
            elif (data_name + "_raw" in self._associated_data):
                return(self._associated_data[data_name + "_raw"])
        elif (isinstance(data_name, tuple) and len(data_name) == 2):
            if (data_name[0] == 'uniform' or data_name[1] == 'uniform'):
                return(('uniform', 'uniform'))
            elif (data_name[0] in self._processings):
                return(data_name)
            elif (data_name[1] in self._processings):
                return((data_name[1],data_name[0]))
        raise ValueError("Invalid name or tuple for data: " + str(data_name))

    def getData(self, data_name, genes_subset=[]):
        """
        Return the NaviData entity corresponding to the data name or tuple

        Args:
            data_name (str or tuple): Identifier of the data
        """
        dTuple = self.getDataTuple(data_name)
        if (genes_subset == []):
            return(self._data[dTuple[0]][dTuple[1]])
        else:
            valid_genes = list()
            dd = self._data[dTuple[0]][dTuple[1]]
            for gene in genes_subset:
                if (gene in dd.genes_names):
                    valid_genes.append(gene)
            return(dd[valid_genes])

    def newNaviCell(self, map_url=None, browser_command=None):
        """
        Link a new NaviCell map to the NaviCom object, allow the use of several display function in a row without erasing the previous ones. The new NaviCell map will be the active map, and the other one cannot be recovered.

        Args:
            map_url (str): URL of the new map, if none specified, 
        """
        if (isinstance(map_url, str)):
            self._map_url = map_url
        elif (self._map_url):
            map_url = self._map_url
        else:
            raise ValueError("A map url has to be provided")
        if (isinstance(browser_command, str)):
            self._browser_command = browser_command
        elif (self._browser_command):
            browser_command = self._browser_command
        # Build options for the navicell connexion
        options = Options()
        options.map_url = map_url
        idx = options.map_url.find('/navicell/')
        options.proxy_url = options.map_url[0:idx] + '/cgi-bin/nv_proxy.php'
        options.browser_command = browser_command
        self._nv = NaviCell(options)
        self._nv.setASyncMode(True)

        self._resetExport()

    def _resetExport(self):
        """ Reset the export status of all table, used when connecting to a new NaviCell instance  """
        # NaviCell export control
        self._exported_annotations = False
        self._browser_opened = False
        self._biotypes = dict()
        for processing in self._exported_data:
            if (isinstance(self._exported_data[processing], bool)):
                self._exported_data[processing] = False
            else:
                for method in self._exported_data[processing]:
                    self._exported_data[processing][method] = False
        # NaviCell import control
        self._uptodate_hugos = False

    def _attachSession(self, map_url, session_id):
        """
            Attach the NaviCom object to a new NaviCell session. Consider that the session is already openend, it is used server side to control the client session.

            Args:
                map_url (str): URL of the new map.
                session_id (str): ID of the session to bind to.
        """
        self.newNaviCell(map_url)
        self._nv.attachSession(str(session_id))
        self._browser_opened = True
        self._resetExport()

    # Load new data
    def loadData(self, fname="data/Ovarian_Serous_Cystadenocarcinoma_TCGA_Nature_2011.txt", keep_mutations_nan=False):
        """
            Load data from a .txt or .ncc file containing several datas, or from a .tsv, .ncd or .nca file containing data from one method.

            Args:
                fname (str): name of the file from which the data should be loaded
                keep_mutations_nan (str): whether nan in mutations data should be considered as no mutation (False) or missing value (True)
        """
        with open(fname) as file_conn:
            ff = file_conn.readlines()
            ll = 0
        # Name the dataset according to the filename, and issue a warning if the name changes
        dname = parseFilename(fname)[0]
        if (dname == "no_name"):
            self.name = dname

        dataRegex = "^M |^GENE"
        annotRegex = "^ANNOTATIONS|^NAME"
        completeRegex = dataRegex + "|" + annotRegex
        methodFromFile = False
        while (ll < len(ff)):
            if (re.search(dataRegex, ff[ll])):
                # Import data
                # Use the method and processing names if they are provided, otherwise deduce them from the filename 
                if (re.search("^M ", ff[ll])):
                    line = re.sub("^M", "", ff[ll].strip()).split("\t")
                    method = line[0].strip()
                    if (len(line) > 1 and line[1] in self._processings):
                        processing = line[1].strip()
                    else:
                        processing = "raw"
                    samples = getLine(ff[ll+1])
                    if (samples[0] == "GENE"):
                        samples = samples[1:]
                    ll += 2
                elif (re.search("^GENE", ff[ll])):
                    fname = os.path.split(fname)[1]
                    dname, processing, method = parseFilename(fname)
                    # Deduction cannot be performed
                    if (methodFromFile):
                        raise ValueError("A type of data must be provided when importing several data in one file")
                    else:
                        methodFromFile = True
                    samples = getLine(ff[ll])[1:]
                    ll += 1
                print("Importing " + method + " data")
                profile_data = dict()
                profile_data["samples"] = oDict()
                profile_data["genes"] = oDict()
                profile_data["data"] = list()
                ii = 0
                for el in samples:
                    profile_data["samples"][el] = ii
                    ii += 1

                gid = 0
                while(ll < len(ff) and not re.search(completeRegex, ff[ll])):
                    dl = getLine(ff[ll])
                    profile_data["data"].append(dl[1:]) # Data in a list at index gene_name
                    profile_data["genes"][dl[0]] = gid
                    gid += 1

                    ll += 1
                if (processing in self._data and method in self._data[processing]):
                    warn("Overwriting data for method " + method + " with processing " + processing)
                new_data = NaviData(profile_data["data"], profile_data["genes"], profile_data["samples"], method, processing)
                self._newProcessedData(method, processing, new_data)
                self.quantifyMutations(method, False)
                if (not "uniform" in self._data):
                    self._defineUniformData(profile_data["samples"], profile_data["genes"])
            elif (re.search(annotRegex, ff[ll])):
                # Import annotations
                print("Importing Annotations")
                if (re.search("^ANNOTATIONS", ff[ll])):
                    annotations_names = getLine(ff[ll+1])
                    if (annotations_names[0] == "NAME"):
                        annotations_names = annotations_names[1:]
                    ll += 2
                elif (re.search("^NAME", ff[ll])):
                    annotations_names = getLine(ff[ll][1:])
                    ll += 1
                annot = dict()
                annot["names"] = list()
                annot["samples"] = list()
                annot["annot"] = list()
                not_all = not "all" in annotations_names
                if (not_all):
                    annot["names"].append("all")
                    annot["annot"].append([1 for ii in range(nb_samples)])
                for name in annotations_names:
                    annot["names"].append(name)
                while(ll < len(ff) and not re.search(completeRegex, ff[ll])):
                    al = getLine(ff[ll])
                    # Gather each annotation for this sample and add all as the first column if necessary
                    if (not_all):
                        annot["annot"].append([1] + al[1:])
                    else:
                        annot["annot"].append(al[1:])
                    annot["samples"].append(al[0])

                    ll = ll+1
                self._annotations = NaviAnnotations(annot["annot"], annot["samples"], annot["names"], dType="annotations")
            else:
                raise ValueError("Incorrect format, file must be a valid file for NaviCell or an aggregation of such files with headers to indicate the type of data")

    def bindNaviData(self, navidata, method, processing):
        """
        Bind a NaviData datatable to the NaviCom object in order to use it 

        Args:
            navidata (NaviData): the NaviData datatable to bind
            method (str): the method used to get the data
            processing (str): the visualisation related processing applied to the data
        """
        assert isinstance(navidata, NaviData), "navidata is not a NaviData object"
        self._newProcessedData(method, processing, navidata)

    def _defineUniformData(self, samples, genes):
        self._data["uniform"] = NaviData( np.array([[1] * len(samples) for nn in genes]), genes, samples, "uniform")
        # TODO change to 1.0 when < is changed to <= for continuous data

    def _newProcessedData(self, method, processing, data, warnings=True):
        """
        Update adequate arrays when processed data are generated
        """
        assert processing in self._processings, "Processing " + processing + " is not handled"
        if (warnings and method in self._data[processing]):
            warn("'" + method + "' already exist for processing '" + processing + "'")
        self._data[processing][method] = data
        self._exported_data[processing][method] = False
        self._nameData(method, processing)

    # Process data
    def quantifyMutations(self, method, keep_nan=False):
        """
        Transform the qualitative mutation datas into a quantitative one, where 1 means a mutation and 0 no mutation.

        Args:
            keep_nan : Should nan values be converted to O (no mutations) or kept as missing data
        """
        for processing in ["raw", "textMutations"]:
            if (method in self._data[processing] and METHODS_TYPE[method.lower()] == "mutations" and self._data[processing][method].data.dtype.char == "U"):
                mutations = NaviData(np.zeros(self._data[processing][method].data.shape), self._data[processing][method].rows_names, self._data[processing][method].columns_names, method, processing)
                for rr in range(len(self._data[processing][method].rows_names)):
                    for cc in range(len(self._data[processing][method].columns_names)):
                        value = self._data[processing][method][rr][cc]
                        if ( re.match("nan|na", value.lower()) ):
                            if (keep_nan):
                                mutations.data[rr][cc] = np.nan
                            else:
                                mutations.data[rr][cc] = 0.
                        elif ( value == "" ):
                            mutations.data[rr][cc] = 0.
                        else:
                            mutations.data[rr][cc] = 1.
                self._newProcessedData(method, "textMutations", self._data[processing][method], False)
                self._data["textMutations"][method].processing = "textMutations"
                self._newProcessedData(method, "raw", mutations, False)

    def defineModules(self, modules_dict=""):
        """
        Defines the modules to use and which module each gene belongs to.

        Args:
            modules_dict : Either a dict indexed by module name or a file name with the description of each module (.gmt file: tab delimited, first column module name, second column description, then list of entities in the module)
        """
        # Gather the composition of each module
        self.modules = dict()
        if (isinstance(modules_dict, dict)):
            self.modules = modules_dict 
        elif (isinstance(modules_dict, str)):
            if (modules_dict != ""):
                with open(modules_dict) as ff:
                    for line in ff.readlines():
                        ll = line.strip().split("\t")
                        module_name = ll[0]
                        self.modules[module_name] = ll[2:]

        # TODO add control that the genes in the modules have data
        """
        # Only keep genes with data
        for module in self.modules:
            keep = list()
            for gene in self.modules[module]:
                if (not gene in self.genes_list):
                    self.modules[module].remove(gene)
        """
        # Count the number of modules each gene belong to
        self._associated_modules = dict()
        for module_name in self.modules.keys():
            for gene in self.modules[module_name]:
                try:
                    self._associated_modules[gene].append(module_name)
                except KeyError:
                    self._associated_modules[gene] = [module_name]

    def averageModule(self, method):
        """
        Perform module averaging for every modules for one data type
        """
        assert method in self._data["raw"], "This type of data is not present"
        assert len(self.modules)>0, "No module have been defined"

        # Calculate average expression for each module
        data = self._data["raw"][method]
        samples = list(data._samples.keys())
        module_expression = dict()
        for module in self.modules:
            module_expression[module] = [0 for sample in samples]
            non_nan = np.array([0 for sample in samples])
            no_data = list()
            for gene in self.modules[module]:
                try:
                    not_nan = np.array([int(not np.isnan(dd)) for dd in data[gene].data])
                    non_nan += not_nan
                    non_nan_data = data[gene].data * not_nan
                    non_nan_data[np.isnan(non_nan_data)] = 0
                    module_expression[module] += non_nan_data
                except IndexError:
                    no_data += [gene]
            for gene in no_data:
                #self.modules[module].remove(gene)
                if (VERBOSE_NAVICOM):
                    print(gene + " from module " + module + " has no " + method + " data")
            module_expression[module] /= non_nan

        # Calculate average module expression for each gene
        gene_module_average = list()
        for gene in data._genes:
            if gene in self._associated_modules:
                gene_module_average.append(np.array([0. for sample in data._samples]))
                for module in self._associated_modules[gene]:
                    gene_module_average[-1] += module_expression[module] / len(self._associated_modules[gene])
            else:
                gene_module_average.append(np.array(list(data[gene])))
                print(gene)

        # Put the averaging in a NaviData structure
        #self._data["moduleAverage"][method] = NaviData(list(module_expression.values()), list(self.modules.keys()), samples) # Usefull if NaviCell allow modules values one day
        self._newProcessedData(method, "moduleAverage", NaviData(gene_module_average, list(data._genes), samples))

    def _pcaComp(self, method, colors=["red", "green", "blue"]):
        """
        Run pca on the data and create a color matrix with the 3 principal components in the three main colors
        """
        print("Not implemented yet")

    # Export data and annotations
    def _exportData(self, method, processing="raw", name=""):
        """
        Export data to NaviCell, can be processed data

        Args:
            method (str) : name of the method to export
            processing (str) : "" to export raw data, processing method to export processed data. See 'averageModule' and '_pcaComponent'
        """
        self._checkBrowser() # TODO Perform processing if necessary
        done_export = False

        if (processing in self._processings):
            if (method == "uniform"): # Uniform data for glyphs
                if (not self._exported_data["uniform"]):
                    print("Exporting 'uniform'  to NaviCell...")
                    self._nv.importDatatables( self._data["uniform"]._makeData(self._nv.getHugoList()), "uniform", getBiotype("uniform") )
                    self._configureDisplay('uniform')
                    done_export = True
                    self._exported_data["uniform"] = True
            elif (method in self._data[processing]):
                if (not self._exported_data[processing][method]):
                    name = self._nameData(method, processing, name)
                    print("Exporting '" + name + "' to NaviCell...")
                    # Processing change the type of data, like discrete data into continuous, or anything to color data
                    biotype = getBiotype(method, processing)
                    self._nv.importDatatables(self._data[processing][method]._makeData(self._nv.getHugoList()), name, biotype)
                    self._configureDisplay(method, processing)
                    self._exported_data[processing][method] = True
                    done_export = True
            elif (method in self._data["distribution"]):
                pass # Exported on creation, TODO change for multiple NaviCell
            else:
                raise KeyError("Method '" + method + "' with processing '" + processing + "' does not exist")
        else:
            raise KeyError("Processing '" + processing + "' does not exist")

        # Uniform data have been defined when other datas have, but do not recquire explicit export
        if (not self._exported_data["uniform"]):
            self._exportData("uniform")

    def completeExport(self, with_processings=list()):
        """
            Export all data available to NaviCell, and perform the required processings on all those data

            Args:
                with_processings (list): list of processings to apply to the data before exporting everything (raw data + processed data)
        """
        assert isinstance(with_processings, list), "'with_processings' must be a list of processings"
        if (len(with_processings) > 0):
            for processing in with_processings:
                if (not processing in PROCESSINGS):
                    raise ValueError("Processing " + processing + " does not exist.")
        else:
            for processing in self._processings:
                for method in self._data[processing]:
                    self._exportData(method, processing)

    def _checkBrowser(self):
        """
        Check if the browser is opened or open it
        """
        if (not self._browser_opened):
            print("Launching browser...")
            self._nv.launchBrowser()
            self._browser_opened = True
        if (not self._uptodate_hugos):
            self._map_hugos = self._nv.getHugoList()
            self._uptodate_hugos = True
        return(self._browser_opened)

    def exportAnnotations(self):
        """
        Export samples annotations to NaviCell
        """
        self._checkBrowser()

        if (not self._exported_annotations):
            self._nv.sampleAnnotationImport(self._annotations._makeData())
            self._exported_annotations = True

    def _configureDisplay(self, method, processing="raw"):
        """
        Changes the Color and Size Configuration for the datatable to the one precised by the user.
        """
        dname = self.getDataName((method, processing))
        if (method == "uniform" or processing == "uniform"):
            # One extra step for uniform data, as grouping does < instead of <=
            dtable = self._data['uniform'].data
            print("Configuring display for uniform")
            color = self._display_config.uniform_color
            self._nv.datatableConfigSetColorAt('', dname, NaviCell.CONFIG_COLOR, NaviCell.TABNAME_SAMPLES, 0, color)
            for tab in [NaviCell.TABNAME_GROUPS]:
                self._nv.datatableConfigSetStepCount('', dname, NaviCell.CONFIG_COLOR, tab, 1)
                self._nv.datatableConfigSetValueAt('', dname, NaviCell.CONFIG_COLOR, tab, 0, 1)
                self._nv.datatableConfigSetColorAt('', dname, NaviCell.CONFIG_COLOR, tab, 0, color)
                self._nv.datatableConfigSetValueAt('', dname, NaviCell.CONFIG_COLOR, tab, 1, 2)
                self._nv.datatableConfigSetColorAt('', dname, NaviCell.CONFIG_COLOR, tab, 1, color)
                self._nv.datatableConfigSetValueAt('', dname, NaviCell.CONFIG_SHAPE, tab, 0, 2)
        elif (getBiotype(method, processing) in CONTINOUS_BIOTYPES):
            ## Color configuration
            dtable = self.getData((method, processing), self._map_hugos).data
            print("Configuring display for " + dname)
            ftable = dtable.flatten()
            ftable.sort()
            # Remove extreme values if applicable
            ptable = ftable[ftable > 0]
            if (len(ptable) > 0):
                keep = math.floor( (1 - self._display_config._excluded) * len(ptable) )
                ptable = ptable[:keep]
                if (len(ptable) > 0):
                    maxval = ptable[-1]
                else:
                    maxval = np.nanmax(ftable)
            else:
                maxval = np.nanmax(ftable)
            ntable = ftable[ftable < 0]
            if (len(ntable) > 0):
                keep = math.ceil( self._display_config._excluded * len(ptable) )
                ntable = ntable[keep:]
                if (len(ntable) > 0):
                    minval = ntable[0]
                else:
                    minval = np.nanmin(ftable)
            else:
                minval = np.nanmin(ftable)
            # Use the same scales for positive and negative values, choose the smallest to enhance contrast
            if (minval * maxval < 0):
                if (-minval > maxval):
                    minval = -maxval
                elif (maxval > -minval):
                    maxval = -minval
            # TODO Remove NaN tables in loadData
            if (np.isnan(minval)): # Imply maxval is also nan
                minval = -1
                maxval = 1

            # Set the color and size for NA
            if (len(ftable[np.isnan(ftable)]) > 0):
                navicell_offset = 1 # First value is nan
                for tab in [NaviCell.TABNAME_SAMPLES, NaviCell.TABNAME_GROUPS]:
                    self._nv.datatableConfigSetColorAt('', dname, NaviCell.CONFIG_COLOR, tab, 0, self._display_config.na_color)
            else:
                navicell_offset = 0

            def setColorConfig(position, value, color):
                for tab in [NaviCell.TABNAME_SAMPLES, NaviCell.TABNAME_GROUPS]:
                    if (tab == NaviCell.TABNAME_GROUPS):
                        value = signif(value/self._display_config._groups_sharpening) # Stretch the scale for groups to have clear colors even with averaging
                    self._nv.datatableConfigSetValueAt('', dname, NaviCell.CONFIG_COLOR, tab, position, value)
                    self._nv.datatableConfigSetColorAt('', dname, NaviCell.CONFIG_COLOR, tab, position, color)

            data = self.getData((processing, method), self._map_hugos)
            if (data.display_config == "gradient"):
                step_count = self._display_config.step_count
                for tab in [NaviCell.TABNAME_SAMPLES, NaviCell.TABNAME_GROUPS]:
                    self._nv.datatableConfigSetStepCount('', dname, NaviCell.CONFIG_COLOR, tab, step_count-1) # NaviCell has one default step for Color
                    self._nv.datatableConfigSetStepCount('', dname, NaviCell.CONFIG_SHAPE, tab, step_count) # But not for Shape
                    self._nv.datatableConfigSetStepCount('', dname, NaviCell.CONFIG_SIZE, tab, step_count) # Nor Size

                if (maxval < 0):
                    maxval = 1
                elif (minval > 0):
                    minval = -1
                if (self._display_config._zero_color != ""):
                    half_count = step_count//2
                    if (half_count != 1):
                        # Negative values
                        if (minval >= 0): minval = -1
                        step = -minval/half_count
                        values_list = [signif(val) for val in np.arange(minval, step/2, step)][:-1]
                        for ii in range(half_count):
                            value = values_list[ii]
                            color = self._display_config._colors[ii]
                            setColorConfig(navicell_offset + ii, value, color)
                        # Zero if present
                        offset = half_count
                        if (step_count%2 == 1):
                            setColorConfig(navicell_offset + offset, 0, self._display_config._colors[half_count])
                            offset += 1
                        # Positive values
                        if (maxval <= 0): maxval = 1
                        step = maxval/half_count
                        values_list = [signif(val) for val in np.arange(0., maxval+step/2, step)][1:]
                        for ii in range(half_count):
                            value = values_list[ii]
                            color = self._display_config._colors[offset + ii]
                            setColorConfig(navicell_offset + offset + ii, value, color)
                    else:
                        if (step_count == 2):
                            values_list = [minval, maxval]
                        else:
                            values_list = [minval, 0, maxval]
                        for ii in range(len(values_list)):
                            setColorConfig(navicell_offset + ii, values_list[ii], self._display_config._colors[ii])
                else:
                    for ii in range(step_count):
                        value = np.percentile(dtable, ii*100/(step_count-1))
                        if (ii==0): value = minval
                        elif (ii==(step_count-1)): value = maxval
                        if ( np.isnan(value) ): value = maxval
                        color = self._display_config._colors[ii]
                        setColorConfig(navicell_offset + ii, value, color)
            else:
                step_count = data.display_config.step_count
                for tab in [NaviCell.TABNAME_SAMPLES, NaviCell.TABNAME_GROUPS]:
                    self._nv.datatableConfigSetStepCount('', dname, NaviCell.CONFIG_COLOR, tab, step_count-1) # NaviCell has one default step for Color
                    self._nv.datatableConfigSetStepCount('', dname, NaviCell.CONFIG_SHAPE, tab, step_count) # But not for Shape
                    self._nv.datatableConfigSetStepCount('', dname, NaviCell.CONFIG_SIZE, tab, step_count) # Nor Size

                # Use the glyph config to set a uniform shape and a color gradient, from a light color to the same color but darker
                v0 = maxval
                colors = [data.display_config.color for ii in range(step_count)]
                prev_value = 0
                divide = len(data._columns)+1
                v0mul = 1.1
                if (divide > 10 * step_count):
                    v0mul *= 10 # Make sure to have a meaningful separation for datasets with a lot of samples (each step in size is 10% of the samples)
                size = data.display_config.min_size
                shape = data.display_config.shape
                ftable = dtable[np.invert(np.isnan(dtable))]
                if (len(ftable) == 0):
                    ftable = dtable
                for ii in range(step_count):
                    value = np.percentile(ftable, ii*100/(step_count-1))
                    if (ii==0): value = minval
                    elif (ii==(step_count-1)): value = maxval
                    if (value == 0): # Make sure that sizes different from min_size apply to a value different from 0 (i.e. 0 has min_size, this is useful for >0 values)
                        value = v0 / divide # The first step is simply different from 0
                        v0 += v0mul * maxval # The others are 10 extra samples steps
                    elif ( np.isnan(value) ):
                        value = prev_value + v0 / divide
                    prev_value = value
                    color = colors[ii]
                    size += 2
                    for tab in [NaviCell.TABNAME_SAMPLES, NaviCell.TABNAME_GROUPS]:
                        self._nv.datatableConfigSetValueAt('', dname, NaviCell.CONFIG_COLOR, tab, navicell_offset + ii, value)
                        self._nv.datatableConfigSetColorAt('', dname, NaviCell.CONFIG_COLOR, tab, navicell_offset + ii, color)
                        self._nv.datatableConfigSetValueAt('', dname, NaviCell.CONFIG_SHAPE, tab, navicell_offset + ii, value)
                        self._nv.datatableConfigSetShapeAt('', dname, NaviCell.CONFIG_SHAPE, tab, navicell_offset + ii, shape)
                        self._nv.datatableConfigSetValueAt('', dname, NaviCell.CONFIG_SIZE, tab, navicell_offset + ii, value)
                        self._nv.datatableConfigSetSizeAt('', dname, NaviCell.CONFIG_SIZE, tab, navicell_offset + ii, size)
                if (np.nanmin(ftable) >= 0):
                    for tab in [NaviCell.TABNAME_SAMPLES, NaviCell.TABNAME_GROUPS]:
                        self._nv.datatableConfigSetSizeAt('', dname, NaviCell.CONFIG_SIZE, tab, navicell_offset, data.display_config.min_size)


            self._nv.datatableConfigSetSampleMethod('', dname, NaviCell.CONFIG_COLOR, NaviCell.METHOD_CONTINUOUS_MEDIAN) # TODO change to MEAN when group mean is corrected to <= instead of <
            if self._display_config.use_absolute_values:
                self._nv.datatableConfigSetSampleAbsoluteValue("", dname, NaviCell.CONFIG_COLOR, True)
            else:
                self._nv.datatableConfigSetSampleAbsoluteValue("", dname, NaviCell.CONFIG_COLOR, False)
        else:
            dtable = self._data[processing][method].data

        ## Size configuration 
        if (dtable.dtype.char == "U"): # String array
            if (len(dtable[dtable=="nan"]) > 0):
                for glyph_id in range(1, MAX_GLYPHS):
                    for tab in [NaviCell.TABNAME_SAMPLES, NaviCell.TABNAME_GROUPS]:
                        self._nv.datatableConfigSetSizeAt("", dname, NaviCell.CONFIG_SIZE, tab, 0, self._display_config.na_size)
        else: # float array TODO add zero if present
            if (len(dtable[np.isnan(dtable)]) > 0):
                for glyph_id in range(1, MAX_GLYPHS):
                    for tab in [NaviCell.TABNAME_SAMPLES, NaviCell.TABNAME_GROUPS]:
                        self._nv.datatableConfigSetSizeAt("", dname, NaviCell.CONFIG_SIZE, tab, 0, self._display_config.na_size)

        for config in [NaviCell.CONFIG_COLOR, NaviCell.CONFIG_SIZE, NaviCell.CONFIG_SHAPE]:
            self._nv.datatableConfigSwitchSampleTab('', dname, config)
            self._nv.datatableConfigApply('', dname, config)
            self._nv.datatableConfigSwitchGroupTab('', dname, config)
            self._nv.datatableConfigApply('', dname, config)
        
    # Display data
    def display(self, perform_list, default_samples="all: 1.0", colors="", module='', reset=True):
        """
            Display data on the NaviCell map

            Args:
                perform_list (list_of_2_or_3-tuple): each tuple (datatable, display_mode[, sample]) must contain the name of the data to display and the mode of display ("glyphN_(color|size|shape)", "barplot", "heatmap" or "map_staining"). Barplots and heatmaps cannot be displayed simultaneously. Several data types can be specified for heatmaps. Specifying "glyph" (without number) will automatically select a new glyph for each data using the same properties (shape, color or size) in glyphs (maximum of 5 glyphs).
                colors : range of colors to use (NOT IMPLEMENTED YET)
                default_samples (str_or_list_of_str) : Samples to use. Only the first sample is used for glyphs and map staining, all default_samples from the list are used for heatmaps and barplots. Use 'all_samples' to use all default_samples or ['annot1:...:annotn', 'all_groups'] to use all groups corresponding to the combinations of annot1...annotn.
        """
        # Correct if the user give a single tuple
        if (isinstance(perform_list, tuple)):
            perform_list = [perform_list]
        assert isinstance(perform_list, list) and len(perform_list)>0, "'perform list' must be a non empty list"
        assert isinstance(perform_list[0], tuple) and (len(perform_list[0]) == 2 or len(perform_list[0]) == 3), "perform list must be a list of (2/3)-tuples"
        self._checkBrowser()
        self.exportAnnotations()
        if (reset):
            self.resetDisplay()

        # Preprocess the perform list to get valid data_name, and export data that have not been exported yet
        if (DEBUG_NAVICOM):
            print(perform_list)
        for perf_id in range(len(perform_list)):
            data_name = perform_list[perf_id][0]
            perform = perform_list[perf_id]
            processing, method = self.getDataTuple(data_name)
            #if (isinstance(data_name, str)):
                #if (not data_name in self._associated_data):
                    #data_name = data_name + "_raw"
                #data_name = self._associated_data[data_name]
            #processing = data_name[0]
            #method = data_name[1]
            #assert processing in self._processings, "Processing " + processing + " does not exist"
            self._exportData(method, processing)
            if (len(perform) >= 3 and perform[2] != default_samples):
                perform_list[perf_id] = (self._data_names[processing][method], perform[1], perform[2])
            else:
                perform_list[perf_id] = (self._data_names[processing][method], perform[1], '')
        self._exportData("uniform")

        # Control that the user does not try to display to many data or use several times the same display
        if (True):
            glyph = dict()
            for gtype in GLYPH_TYPES:
                glyph[gtype] = [False] * MAX_GLYPHS
            glyph_samples = [""] * MAX_GLYPHS
            glyph_data = [""] * MAX_GLYPHS
            glyph_set = False
            heatmap = False
            barplot = False
            barplot_data = ""
            map_staining = False
            default_samples = self._processSampleSelection(default_samples)
            samples = default_samples
            lastSampleWasDefault = True
            valid_default = (len(default_samples) == 1 and default_samples != "all_groups" and default_samples != "all_samples")
        # Perform the display depending of the selected mode
        for perform in perform_list:
            all_samples = False
            all_groups = False
            data_name = perform[0]
            dmode = perform[1]
            dmode = dmode.lower()
            # Check groups in NaviCell and get a valid list of samples, reload default if not the last used
            if (perform[2] == ''):
                if (not lastSampleWasDefault):
                    samples = self._processSampleSelection(default_samples)
                    lastSampleWasDefault = True
            else:
                samples = self._processSampleSelection(perform[2])
                lastSampleWasDefault = False
            if (samples == "all_groups"):
                all_groups = True
            elif (samples == "all_samples"):
                all_samples = True

            if (re.search("^(glyph|color|size|shape)", dmode)):
                glyph_set = True
                # Extract the glyph id and the setup
                parse_setup = dmode.split("_")
                glyph_setup = parse_setup
                if (len(parse_setup) == 2):
                    try:
                        glyph_setup = [parse_setup[1] + str(int(parse_setup[0][-1]))]
                    except ValueError:
                        glyph_setup = [parse_setup[1]]
                elif (len(parse_setup) != 1):
                    raise ValueError("Glyph specification '" + dmode + "' incorrect")
                try: # Use the number if specified...
                    glyph_number = int(glyph_setup[0][-1])
                    glyph_type = glyph_setup[0][:-1]
                except ValueError: # ... or use the first free slot for the type selected
                    glyph_type = glyph_setup[0]
                    glyph_number = 1
                    while (glyph[glyph_type][glyph_number-1]):
                        glyph_number += 1
                glyph_id = glyph_number - 1
                
                if (not glyph_number in range(1, MAX_GLYPHS+1)):
                    raise ValueError("Glyph number must be in [1," + str(MAX_GLYPHS) + "]")
                if (not glyph_type in GLYPH_TYPES):
                    raise ValueError("Glyph type must be one of " + str(GLYPH_TYPES))
                if (glyph[glyph_type][glyph_number-1]):
                    raise ValueError(glyph_type + " for glyph " + str(glyph_number) + " has already been specified")
                glyph[glyph_type][glyph_number-1] = True
                if (len(samples) != 1 or samples == "all_groups" or samples == "all_samples"):
                    raise ValueError("Only one group or sample can be used for glyphs")

                if (lastSampleWasDefault):
                    pass
                elif (glyph_samples[glyph_id] == ""):
                    glyph_samples[glyph_id] = samples[0]
                elif (glyph_samples[glyph_id] != samples[0]):
                    raise ValueError("Only one sample can be specified per glyph")

                glyph_data[glyph_id] = data_name

                cmd="self._nv.glyphEditorSelect" + glyph_type.capitalize() + "Datatable('" + module +  "', " + str(glyph_number) + ", '" + data_name + "')"
                if (DEBUG_NAVICOM):
                    print(cmd)
                exec(cmd)
            elif (re.search("map_?staining", dmode)):
                assert valid_default, "Only one sample can be used for map staining"
                if (not map_staining):
                    self._nv.mapStainingEditorSelectDatatable(module, data_name)
                    self._nv.mapStainingEditorSelectSample(module, samples[0])
                    self._nv.mapStainingEditorApply(module)
                    map_staining = True
                else:
                    raise ValueError("Map staining can only be applied once, use a separate call to the display function to change map staining")
            elif (re.search("heatmap", dmode)):
                if (barplot):
                    raise ValueError("Heatmaps and barplots cannot be applied simultaneously, use a separate call to the display function to perform the heatmap")
                heatmap = True
                # Select data
                self._nv.heatmapEditorSelectDatatable(module, self._hdid, data_name)
                self._hdid += 1
                # Select samples
                if (all_samples):
                    self._nv.heatmapEditorAllSamples(module)
                elif (all_groups):
                    self._nv.heatmapEditorAllGroups(module)
                elif (self._hsid == 0):
                    for spl in samples:
                        self._nv.heatmapEditorSelectSample(module, self._hsid, spl)
                        self._hsid += 1
                    self._nv.heatmapEditorApply(module)
            elif (re.search("barplot", dmode)):
                if (heatmap):
                    raise ValueError("Heatmaps and barplots cannot be applied simultaneously, use a separate call to the display function to perform the barplot")
                # Check that it does not try to add new data, and simply adds samples # TODO Remove as samples cannot be added (resetDisplay at the beginning)
                if (barplot and data_name != barplot_data and not re.search("all|groups|samples", data_name)):
                    raise ValueError("Barplot has already been set with different data, use a separate call to the display function to perform another barplot")
                barplot = True
                barplot_data = data_name
                self._nv.barplotEditorSelectDatatable(module, data_name)
                # Select samples
                if (all_samples):
                    self._nv.barplotEditorAllSamples(module)
                elif (all_groups):
                    self._nv.barplotEditorAllGroups(module)
                elif (self._bid == 0):
                    for spl in samples:
                        self._nv.barplotEditorSelectSample(module, self._bid, spl)
                        self._bid += 1
                    self._nv.barplotEditorApply(module)
            else:
                raise ValueError("'" + dmode + "' drawing mode does not exist")

        # Check that datatables are selected for all glyphs features (until default has been added)
        # or complete, then apply the glyphs configuration
        default_samples = self._processSampleSelection(default_samples)
        if (glyph_set):
            for glyph_id in range(MAX_GLYPHS):
                nsets = sum(1 for gt in GLYPH_TYPES if glyph[gt][glyph_id])
                if (nsets > 0):
                    if (glyph_samples[glyph_id] != ""):
                        self._nv.glyphEditorSelectSample(module, glyph_id+1, self._processSampleSelection(glyph_samples[glyph_id]))
                    elif (valid_default):
                        print("Using default sample for glyph " + str(glyph_id+1))
                        self._nv.glyphEditorSelectSample(module, glyph_id+1, default_samples[0])
                    else:
                        raise ValueError("No samples specified for glyph " + str(glyph_id+1) + " and default_samples is invalid")
                    if (not glyph["color"][glyph_id]):
                        self._nv.glyphEditorSelectColorDatatable(module, glyph_id+1, glyph_data[glyph_id])
                    if (not glyph["shape"][glyph_id]):
                       self._nv.glyphEditorSelectShapeDatatable(module, glyph_id+1, glyph_data[glyph_id])
                    if (not glyph["size"][glyph_id]):
                        self._nv.glyphEditorSelectSizeDatatable(module, glyph_id+1, glyph_data[glyph_id])
                    self._nv.glyphEditorApply(module, glyph_id+1)
        

    def resetDisplay(self):
        """
        Reset the data and samples selections in NaviCell
        """
        for ii in range(self._bid):
            self._nv.barplotEditorSelectSample('', ii, '')
        self._nv.barplotEditorSelectDatatable('', '')
        self._nv.drawingConfigSelectBarplot('', False)

        for ii in range(self._hsid):
            self._nv.heatmapEditorSelectSample('', ii, '')
        for ii in range(self._hdid):
            self._nv.heatmapEditorSelectDatatable('', ii, '')
        self._nv.drawingConfigSelectHeatmap('', False)

        for gid in range(1, MAX_GLYPHS):
            for gt in GLYPH_TYPES:
                exec("self._nv.glyphEditorSelect" + gt.capitalize() + "Datatable('', " + str(gid) + ", '')")
            self._nv.glyphEditorSelectSample('', gid, '')
            self._nv.drawingConfigSelectGlyph('', gid, False)
        
        self._nv.drawingConfigSelectMapStaining('', False)
        self._nv.drawingConfigApply('')

        # Reset the counters
        self._bid = 0
        self._hsid = 0
        self._hdid = 0

    def _resetAnnotationsSelection(self, module=''):
        for annot in self._annotations._annotations:
            self._nv.sampleAnnotationSelectAnnotation(module, annot, False)
        self._nv.sampleAnnotationApply(module)

    def _selectAnnotations(self, annotations, module=''):
        """
        Select annotations on the NaviCell map
        """
        if (isinstance(annotations, str)):
            self._nv.sampleAnnotationSelectAnnotation(module, annotations, True)
        elif (isinstance(annotations, list)):
            for annot in annotations:
                self._nv.sampleAnnotationSelectAnnotation(module, annot, True)
        else:
            raise ValueError("'annotations' must be a string or a list")
        self._nv.sampleAnnotationApply(module)

    def _processSampleSelection(self, current_samples):
        """
        Process a list of samples or groups to a list of samples/groups names exportable to NaviCell or to "all_groups"/"all_samples" for heatmap and barplot, and select the correct groups in NaviCell
        """

        self._resetAnnotationsSelection()
        # Make sure current_samples is a list
        all_groups = False
        if (isinstance(current_samples, str)):
            current_samples = [current_samples]

        # It is possible to select all samples or all groups on heatmap and barplot
        if (current_samples[0] == "all_samples" or current_samples[0] == "samples"):
            return "all_samples"
        elif (current_samples[0] == "all" or current_samples[0] == "all: 1.0"):
            self._selectAnnotations("all")
            return ["all: 1.0"]
        elif (len(current_samples) > 1 and (current_samples[1] == "all_groups" or current_samples[1] == "groups")):
            all_groups = True

        refGroupsList = []
        first_groups = True
        # Select the groups that must be selected to produce the composite groups required
        for sample in current_samples:
            groups = self._processGroupsName(sample)[0]
            # Check that all groups are compatible in the annotations selected (because lower order composition are not generated). No check for individual samples
            if (len(groups) >= 1):
                if (first_groups): # Select the set of annotations for the first group
                    if (DEBUG_NAVICOM):
                        print("Selecting " + str(groups))
                    for group in groups:
                        self._selectAnnotations(group) 
                        refGroupsList.append(group)
                        first_groups = False
                else: # Control that all other groups are compatible
                        assert len(group)==0 or len(refGroupsList)==0 or len(group)==len(refGroupsList), "Groups combinations are not compatible, different number of groups"
                        for group in groups:
                            assert group in refGroupsList, "Groups combinations are not compatibles as " + group + " is not in " + str(refGroupsList)

        if (all_groups):
            return "all_groups"
        return current_samples

    def _processGroupsName(self, groupName):
        """
        Process a group selection string and return the names of the individual groups to select and the corresponding values selected.
        """
        selections = groupName.split(";")
        groups = list()
        values = list()
        for select in selections:
            subName = select.split(":")
            group = subName[0].strip()
            if (group in self._annotations._annotations): # Groups
                value = subName[1].strip()
                groups.append(group)
                values.append(value)
            elif (not (group in self._annotations._samples or re.match("sub", group) or group == "NaN")): # Samples
                if (len(subName) > 1):
                    raise ValueError("Annotation " + group + " does not exist")
                else:
                    raise ValueError("Sample " + group + " does not exist")
        return((groups, values))

    def completeDisplay(self, sample="all: 1.0", processing="raw"):
        """
            Display as many data as possible on one map. If available draw mRNA as map staining, CNA as barplot, and mutations, methylation, proteomics and miRNA as glyphs.

            Args:
                sample (str): The sample or group to display
                processing (str): Processing for the data to display
        """
        disp_selection = []

        # TODO put everything as barplots when available in NaviCell
        mrna = self.getTranscriptomicsData(processing)
        if (len(mrna) > 0):
            disp_selection.append( ((processing, mrna[0]), "map_staining") )
        cna = self.getGenomicData(processing)
        if (len(cna) > 0):
            disp_selection.append( ((processing, cna[0]), "heatmap") )

        mut = self.getMutationsData(processing)
        if (len(mut) > 0):
            disp_selection.append( ((processing, mut[0]), "size1") )
        methylation = self.getMethylationData(processing)
        if (len(methylation) > 0):
            disp_selection.append( ((processing, methylation[0]), "size2") )
        mirna = self.getmiRNAData(processing)
        if (len(mirna) > 0):
            disp_selection.append( ((processing, mirna[0]), "size3") )
        prot = self.getProteomicsData(processing)
        if (len(prot) > 0):
            disp_selection.append( ((processing, prot[0]), "size4") )

        # Display all the information
        if (len(disp_selection) > 0):
            self.display(disp_selection, sample)
        else:
            warn("No data to display using completeDisplay")

    def getTranscriptomicsData(self, processing="raw"):
        """
        Returns the names of the mRNA datatables in the dataset
        """
        return(self.getMRNAData(processing))
    def getMRNAData(self, processing="raw"):
        """
            Returns the names of the mRNA datatables in the dataset
        """
        mrna_datas = list()
        lprocessing = [proc.lower() for proc in self._data[processing]]
        listprocessing = list(self._data[processing].keys())
        for mrna in TYPES_SPEC["mRNA"][0]:
            if (mrna in lprocessing):
                mrna_datas.append( listprocessing[lprocessing.index(mrna)] )
        for method in self._data[processing]:
            if (re.search("mrna", method.lower()) and not method.lower() in mrna_datas):
                mrna_datas.append(method)
        if (len(mrna_datas) == 0):
            warn("No mRNA data available")
        return(mrna_datas)

    def getmiRNAData(self, processing="raw"):
        """
            Returns the names of the miRNA datatables in the dataset
        """
        mirna_datas = list()
        lprocessing = [proc.lower() for proc in self._data[processing]]
        listprocessing = list(self._data[processing].keys())
        for mirna in TYPES_SPEC["miRNA"][0]:
            if (mirna in lprocessing):
                mirna_datas.append( listprocessing[lprocessing.index(mirna)] )
        for method in self._data[processing]:
            if (re.search("mirna", method.lower()) and not method.lower in mirna_datas):
                mirna_datas.append(method)
        if (len(mirna_datas) == 0):
            warn("No miRNA data available")
        return(mirna_datas)
    
    def getGenomicData(self, processing="raw"):
        """
            Returns the names of CNV datatables in the dataset
        """
        return(self.getCNAData(processing))
    def getCNAData(self, processing="raw"):
        """
        Returns the names of CNV datatables in the dataset
        """
        cnv_datas = list()
        dcnv_datas = list()
        for method in self._data[processing]:
            if (method.lower() in TYPES_SPEC["cCNA"][0]):
                cnv_datas.append(method)
            if (method.lower() in TYPES_SPEC["dCNA"][0]):
                dcnv_datas.append(method)
        if (len(dcnv_datas + cnv_datas) == 0):
            warn("No copy number data available")
        return(cnv_datas+dcnv_datas)

    def getMethylationData(self, processing="raw"):
        """
        Returns the names of the methylation datatables in the dataset
        """
        methylation_datas = list()
        for method in self._data[processing]:
            if ( method.lower() in TYPES_SPEC["methylation"][0] or re.search("methylation", method.lower()) ):
                methylation_datas.append(method)
        if (len(methylation_datas) == 0):
            warn("No methylation data available")
        return(methylation_datas)
    
    def getProteomicsData(self, processing="raw"):
        """
        Returns the names of the proteomics datatables in the dataset
        """
        proteomics_datas = list()
        for method in self._data[processing]:
            if ( method.lower() in TYPES_SPEC["protein"][0] or re.search("protein", method.lower()) ):
                proteomics_datas.append(method)
        if (len(proteomics_datas) == 0):
            warn("No proteomics data available")
        return(proteomics_datas)
    
    def getMutationsData(self, processing="raw"):
        """
        Returns the names of the mutations datatables in the dataset
        """
        mutations_datas = list()
        for method in self._data[processing]:
            if ( method.lower() in TYPES_SPEC["mutations"][0] or re.search("mutations", method.lower()) ):
                mutations_datas.append(method)
        if (len(mutations_datas) == 0):
            warn("No mutations data available")
        return(mutations_datas)

    def selectDataFromBiotype(self, data_spec, processing="raw", restrict=ALL_ALIASES):
        """
            Select the name of the data based on biological types.

            Args:
                data_spec (str): Biological type. mRNA, CNA, proteomics, mutations, methylation and miRNA are currently implemented. See navicom.BIOTYPES_ALIASES for the complete list of aliases
                restrict (list): 
        """
        data_spec = data_spec.upper()
        assert data_spec in restrict + ["NO", ""], "Invalid biotype: '" + data_spec + "'"
        if (data_spec in ["NO", ""]):
            return ""
        elif (data_spec in MRNA_ALIASES):
            datas = self.getMRNAData(processing)
            if (len(datas) > 0):
                return datas[0]
        elif (data_spec in DNA_ALIASES):
            datas = self.getCNAData(processing)
            if (len(datas) > 0):
                return datas[0]
        elif (data_spec in METHYLATION_ALIASES):
            datas = self.getMethylationData(processing)
            if (len(datas) > 0):
                return datas[0]
        elif (data_spec in PROTEIN_ALIASES):
            datas = self.getProteomicsData(processing)
            if (len(datas) > 0):
                return datas[0]
        return ""

    def displayMethylome(self, samples="all: 1.0", processing="raw", background="mRNA", methylation="size"):
        """
            Display the methylation data as glyphs or heatmap on the NaviCell map, with mRNA expression of gene CNV as map staining
            Args:
                background (str) : Data used for the map staining (CNV, mRNA or no data)
                processing (str) : Processing of the data to use
                methylation (str): The display mode for the methylation data (either 'heatmap' or 'size')
        """
        # Groups cannot be used for now because of limitations in NaviCell unless the median is taken as grouping operation
        assert methylation in ["glyph", "glyphs", "heatmap", "size", "glyph_size"], "Cannot use " + methylation + " to display methylation data"
        if (methylation != "heatmap"): methylation="size" # TODO Change default to barplot when available
        assert processing in self._data, "Processing " + processing + " does not exist"

        # Select all methylation data and display as heatmap
        disp_selection = list()
        methods = self.getMethylationData(processing)
        if (len(methods) > 0):
            disp_selection.append( (self.getDataName((processing, methods[0])), methylation) ) # TODO Change to barplot when several datatables can be used
        method = self.selectDataFromBiotype(background)
        if (method != ""):
            disp_selection.append( (self.getDataName((processing, method)), "map_staining") )
        if (DEBUG_NAVICOM):
            print(disp_selection)
            print(samples)
        if (len(disp_selection) > 0):
            self.display(disp_selection, samples)
        else:
            warn("No valid data for methylome display")

    def displayOmics(self, dataName, group="all: 1.0", samplesDisplay="", samples=list(), binsNb=10):
        """
        Display one -omics datatable as map staining, with optionnaly some extra information displayed on top (samples as heatmap or barplot, mutations as glyphs, a glyph for the most highly expressed genes, distribution as heatmap)
        Args:
            dataName (str or tuple): name or identifier of the data.
            group (str): Identifier of the group to display
            samplesDisplay (str): Channel where the individual samples should be displayed (heatmap or barplot)
            samples (list or str): list of samples to display, or a string specifying how such a list should be built ('quantiles' to get the distribution of values)
            nbOfSamples (int): number of individual samples to display, ignored if samples is a list
        """
        allowedDisplays = ["", "heatmap", "barplot"]
        assert samplesDisplay in allowedDisplays, "samplesDisplay must one of " + str(allowedDisplays)
        dataName = self.getDataName(dataName)
        self.display([(dataName, "map_staining")], group)
        if (samplesDisplay != ""):
            if (isinstance(samples, list) and len(samples) > 0):
                self.display([(dataName, samplesDisplay)], samples, reset=False)
            elif (isinstance(samples, str) and samples != ""):
                if (samples == "quantiles"):
                    distName, distSamples = self._generateDistributionData(dataName, group, binsNb)
                    #self._data["distribution"][distName].exportToNaviCell(self._nv, TYPES_BIOTYPE['mRNA'], distName)
                    self.display([((distName, "distribution"), samplesDisplay)], distSamples, reset=False)
                else:
                    self.display([(dataName, samplesDisplay)], [samples], reset=False)

    def _generateDistributionData(self, dataName, group, binsNb=10):
        """
        Compute distribution of values for all genes for one type of data. Use the same scale for all genes. The distribution is centered on 0 if it is included, so that it is easy to see if a gene is over- or under-expressed.
        """
        groups, values = self._processGroupsName(group)
        if (len(groups) < 1):
            raise ValueError("Cannot generate a distribution without a valid group")
        # Each distribution 
        distName = dataName + "_" + re.sub(" ", "_", group) + "_" + str(binsNb)
        distSamples = ["sub" + str(ii) for ii in range(binsNb)] + ["NaN"]
        if (distName in self._data["distribution"]):
            return(distName)

        # Identify the samples selected by the group definition
        samples = self._annotations._samplesPerCategory[groups[0]][values[0]]
        for idx in range(1, len(groups)):
            to_drop = list()
            for spl in samples:
                if (not spl in self._annotations._samplesPerCategory[groups[idx]][values[idx]]):
                    to_drop.append(spl)
            for spl in to_drop:
                samples.remove(spl)

        # Build the distribution dataset
        data = self.getData(dataName)[samples]
        minq = np.nanmin(data.data)
        maxq = np.nanmax(data.data)
        step = (maxq-minq)/binsNb
        if (minq * maxq < 0):
            step = max(-minq/(binsNb/2), maxq/(binsNb/2))
        qseq = np.arange(minq, maxq + step * 1.01, step)
        newData = list()
        for gene in data._genes:
            newData.append([0 for ii in range(binsNb+1)])
            for value in data[gene]:
                if (np.isnan(value)):
                    newData[-1][binsNb] += 1
                else:
                    idx = 0
                    while (value > qseq[idx+1]):
                        idx += 1
                    newData[-1][idx] += 1
        self._newProcessedData( distName, "distribution", NaviData(newData, data._genes, distSamples) )

        return(distName, distSamples)
    
    def displayMutations(self, sample="all: 1.0", background="CNA", background_sample="", processing="raw"):
        """
            Highlight mutated genes with glyphs for one sample or group and add some genomic data in the background.

            Args:
                samples (str): Sample or group to display.
                background (str): Datatable to display in the background.
        """
        assert isinstance(sample, str)
        if (background_sample == ""):
            background_sample = sample
        else:
            assert isinstance(background_sample, str)

        disp_selection = []

        mutations = self.getMutationsData()
        assert len(mutations) > 0, "No mutations data available!"
        disp_selection.append( ((processing, mutations[0]), "size1", sample) )

        background = self.selectDataFromBiotype(background, processing)
        if (background != ""):
            disp_selection.append( ((processing, background), "map_staining", background_sample) )

        self.display(disp_selection)

    def displayMutationsWithGenomics(self, sample="all: 1.0", processing="raw"):
        """
            Display mutations as glyphs, with expression as map staining and copy number variations as barplots
        """
        disp_selection = []

        mrna = self.getTranscriptomicsData(processing)
        if (len(mrna) > 0):
            disp_selection.append( ((processing, mrna[0]), "map_staining") )
        cna = self.getGenomicData(processing)
        if (len(cna) > 0):
            disp_selection.append( ((processing, cna[0]), "heatmap") )
        mut = self.getMutationsData(processing)
        if (len(mut) > 0):
            disp_selection.append( ((processing, mut[0]), "size1") )


        if (len(disp_selection) > 0):
            self.display(disp_selection, sample)
        else:
            warn("No data to display using displayMutationsWithGenomics")

    def displayExpression(self, sample="all: 1.0", processing="raw"):
        """
            Display mRNA expression data with proteomics data as barplot
        """
        disp_selection = []

        mrna = self.getTranscriptomicsData(processing)
        if (len(mrna) > 0):
            disp_selection.append( ((processing, mrna[0]), "map_staining") )

        if (len(disp_selection) > 0):
            self.display(disp_selection, sample)
        else:
            warn("No data to display using displayExpression")

    def displayExpressionWithMutations(self, sample="all: 1.0", processing="raw"):
        """
            Display mutations as glyphs, with expression as map staining
        """
        disp_selection = []

        mrna = self.getTranscriptomicsData(processing)
        if (len(mrna) > 0):
            disp_selection.append( ((processing, mrna[0]), "map_staining") )
        mut = self.getMutationsData(processing)
        if (len(mut) > 0):
            disp_selection.append( ((processing, mut[0]), "size1") )

        if (len(disp_selection) > 0):
            self.display(disp_selection, sample)
        else:
            warn("No data to display using displayExpressionWithMutations")

    def displayExpressionWithCopyNumber(self, sample="all: 1.0", processing="raw"):
        """
            Display mRNA expression data with proteomics data as barplot
        """
        disp_selection = []

        mrna = self.getTranscriptomicsData(processing)
        if (len(mrna) > 0):
            disp_selection.append( ((processing, mrna[0]), "map_staining") )
        cna = self.getGenomicData(processing)
        if (len(cna) > 0):
            disp_selection.append( ((processing, cna[0]), "heatmap") )

        if (len(disp_selection) > 0):
            self.display(disp_selection, sample)
        else:
            warn("No data to display using displayExpressionWithCopyNumber")

    def displayExpressionWithProteomics(self, sample="all: 1.0", processing="raw"):
        """
            Display mRNA expression data with proteomics data as barplot
        """
        disp_selection = []

        mrna = self.getTranscriptomicsData(processing)
        if (len(mrna) > 0):
            disp_selection.append( ((processing, mrna[0]), "map_staining") )
        prot = self.getProteomicsData(processing)
        if (len(prot) > 0):
            disp_selection.append( ((processing, prot[0]), "size4") )

        if (len(disp_selection) > 0):
            self.display(disp_selection, sample)
        else:
            warn("No data to display using displayExpressionWithProteomics")

    def displayExpressionWithmiRNA(self, sample="all: 1.0", processing="raw"):
        """
            Display mRNA expression data with miRNA as barplot
        """
        disp_selection = []

        mrna = self.getTranscriptomicsData(processing)
        if (len(mrna) > 0):
            disp_selection.append( ((processing, mrna[0]), "map_staining") )
        mirna = self.getmiRNAData(processing)
        if (len(mirna) > 0):
            disp_selection.append( ((processing, mirna[0]), "size3") )

        if (len(disp_selection) > 0):
            self.display(disp_selection, sample)
        else:
            warn("No data to display using displayExpressionWithmiRNA")

    def displayExpressionWithMethylation(self, sample="all: 1.0", processing="raw"):
        """
            Display mRNA expression data with Methylation as barplot
        """
        disp_selection = []

        mrna = self.getTranscriptomicsData(processing)
        if (len(mrna) > 0):
            disp_selection.append( ((processing, mrna[0]), "map_staining") )
        meth = self.getMethylationData(processing)
        if (len(meth) > 0):
            disp_selection.append( ((processing, meth[0]), "size2") )

        if (len(disp_selection) > 0):
            self.display(disp_selection, sample)
        else:
            warn("No data to display using displayExpressionWithMethylation")

    def _colorsOverlay(self, red="uniform", green="uniform", blue="uniform", processing=""):
        """
        Create a dataset where values are colors. The color is calculated according to three datasets.

        Args:
            red : data name or tuple (processing, method)
            green : data name or tuple (processing, method)
            blue : data name or tuple (processing, method)
        """
        assert red != "uniform" or green != "uniform" or blue != "uniform", "You must choose a datatable"
        # TODO export to NaviCell and display
        colors = [red, green, blue]
        mset = ""
        # Empty string table
        dims = self._data["uniform"].data.shape
        dataset = np.zeros(dims, '<U7')
        for rr in range(dims[0]):
            for cc in range(dims[1]):
                dataset[rr,cc] = "#"
        for col in colors:
            if (col == "uniform"):
                for rr in range(dims[0]):
                    for cc in range(dims[1]):
                        dataset[rr,cc] += "00" # Default to black
            else:
                # Pick the datatable
                if (processing == ""):
                    processing, method = getDataTuple(col)
                elif (not processing in self._data):
                    raise ValueError("Processing " + processing + " does not exist")
                elif (not col in self._data[processing]):
                    raise ValueError("Method \"" + col + "\" does not exist with processing \"" + processing + "\"")
                else:
                    method = col
                if (processing != "raw"):
                    mset += processing + "_"
                mset += method + "_"
                # Input the value in the new dataset
                minval = np.nanmin(self._data[processing][method].data)
                maxval = np.nanmax(self._data[processing][method].data)
                if (np.isnan(minval) or np.isnan(maxval)):
                    warn("Datatable (" + processing + ", " + method + ") does not contain any value.")
                    for rr in range(dims[0]):
                        for cc in range(dims[1]):
                            dataset[rr,cc] = "00"
                else:
                    for rr in range(dims[0]):
                        for cc in range(dims[1]):
                            value = self._data[processing][method].data[rr,cc]
                            if (np.isnan(value)):
                                value = minval
                            intensity = re.sub("0x", "", hex(int( 16 * (value - minval) / (maxval-minval) )) )
                            if (len(intensity) == 0):
                                intensity = "0" + intensity
                            dataset[rr,cc] += intensity
        mset = re.sub("_$", "", mset)
        # TODO See if mset is used as the method for export
        self._data["colors"][mset] = NaviData(dataset, self._data[processing][method].rows, self._data[processing][method].columns, method="unknown", processing="colors")

    # Saving data
    def saveAllData(self, folder="", sepFiles=False, keep_processings = list()):
        """
        Save all data in an .ncc file. Does not save the distribution nor color data.

        Args:
            folder (str): folder where the data will be save, the name is automatically attributed from the name of the dataset, the method and the processing.
            sepFiles (bool): whether the data should be saved in a single file or in separated files.
            keep_processings (list): list of processings to keep (by default, all processings except the distribution which is very specific to a sample).
        """
        if (folder != ""):
            folder = re.sub("/?$", "/", folder)
        fname = folder + self.name + ".ncc"
        print("Saving as " + fname)
        if (sepFiles):
            wmode = "w"
        else:
            wmode = "a"
            ff = open(fname, "w")
            ff.close()
        # Build a custom list of processings, do not save data built specifically for NaviCell
        allProcessings = list(self._data)
        allProcessings.remove("uniform")
        allProcessings.remove("distribution")
        allProcessings.remove("colors")
        if (len(keep_processings) > 0):
            allProcessings = list()
            for processing in keep_processings:
                assert processing in self._data, "Processing '" + processing + "' does not exist"
                allProcessings.append(processing)
        allProcessings = list(set(allProcessings))
        for processing in allProcessings:
            for method in self._data[processing]:
                print("Saving " + processing + ", " + method)# + ", " + str(self._data[processing][method]))
                self._data[processing][method].saveData(fname, wmode)
        for method in self._data["textMutations"]:
            self._data["textMutations"][method].saveData(fname, wmode)
        print("Saving Annotations")
        self._annotations.saveData(fname, wmode)

    def saveData(self, method, processing="raw", folder="./"):
        """
        Save the data in a file that can be exported to NaviCell or imported in NaviCom
        """
        # TODO authorize to provide a list to save a custom dataset
        if (folder != ""):
            folder = re.sub("/?$", "/", folder)
        if (processing in self._data):
            if (method in self._data[processing]):
                self._data[processing][method].saveData(baseName=folder+self.name)
            else:
                raise ValueError("Method " + method + " does not exist with processing " + processing)
        else:
            raise ValueError("Processing " + processing + " does not exist")

    def saveAnnotations(self, folder="./"):
        """
        Save the annotations in a file than can be exported to NaviCell or imported in NaviCom
        """
        if (folder != ""):
            folder = re.sub("/?$", "/", folder)
        self._annotations.saveData(folder+self.name)

