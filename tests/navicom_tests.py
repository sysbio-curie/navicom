#!/usr/bin/python3
#-*-coding:utf-8-*-
# TODO Test if the code works when non annotations are provided
import time
itime = time.time()
from navicom import *; navicom.DEBUG_NAVICOM = True
nc = NaviCom(map_url='https://navicell.curie.fr/navicell/maps/cellcycle/master/index.php', fname="data/Ovarian_Serous_Cystadenocarcinoma_TCGA_Nature_2011.txt", display_config = DisplayConfig(5, na_color="ffffff"))
# nc = NaviCom(map_url='https://navicell.curie.fr/navicell/maps/cellcycle/master/index.php', fname="data/Ovarian_Serous_Cystadenocarcinoma_TCGA_Nature_2011.txt", browser_command="chromium-browser --allow-file-access-from-files %s")
print("NaviCom loading: " + str(time.time() - itime)); itime=time.time()
nc.displayMutations('TCGA.04.1331.01')
print("Mutations display " + str(time.time() - itime)); itime=time.time()
nc.completeDisplay('TCGA.04.1331.01')
print("Complete display: " + str(time.time() - itime)); itime=time.time()

nc.completeDisplay()
nc.displayMutations('TCGA.04.1331.01')

nc.displayMethylome(['TCGA.04.1331.01'], "raw", "mRNA", "size")

for alias in navicom.ALL_ALIASES:
    nc.selectDataFromBiotype(alias)
nc.displayMutations('TCGA.04.1331.01')

nc.listData()
nc.getCNAData()
nc.getMRNAData()
nc.getMethylationData()
nc.getProteomicsData()
nc.getMutationsData()

nc._exportData("log2CNA")

nc.listAnnotations()

nc.displayMethylome(['TCGA.04.1331.01'], "raw", "mRNA", "size")
nc.displayOmics('log2CNA', 'OS_STATUS: LIVING', "barplot")
nc.displayOmics('log2CNA', 'OS_STATUS: LIVING', "barplot", '')

nc._colorsOverlay("mrna_median", "log2CNA", processing="raw")
nc.listData()
nc.saveData( "mrna_median_log2CNA", "colors")

nc.saveAllData()
nc.loadData("data/Ovarian_Serous_Cystadenocarcinoma_TCGA_Nature_2011_gistic.tsv")
nc.loadData("Ovarian_Serous_Cystadenocarcinoma_TCGA_Nature_2011.ncc")

dd=nc.generateDistributionData(nc.getDataName('log2CNA'), 'OS_STATUS: LIVING')
nc.distData[dd[0]].exportToNaviCell(nc.nv, TYPES_BIOTYPE['mRNA'], dd[0])

nc.exportAnnotations()
nc.displayOmics('log2CNA', 'OS_STATUS: LIVING', "barplot", 'quantiles')

nc.displayOmics('log2CNA', 'OS_STATUS: NA', "barplot", 'TCGA.04.1331.01')

nc.defineModules("data/cellcycle_v1.0.gmt")
nc.averageModule("gistic") # TODO Warning might be to fix

nc.display([('log2CNA', 'barplot'), ('gistic', 'shape2', 'TCGA.04.1331.01'), ('log2CNA', 'size2', 'TCGA.04.1331.01')], ['OS_STATUS: NA; SEQUENCED: NA'])

nc.displayMethylome(['TCGA.04.1331.01'], "raw", "mRNA", "size")

nc.display([('log2CNA', 'barplot')], ['OS_STATUS: NA; SEQUENCED: NA'])
nc.resetDisplay()

nc.display([('log2CNA', 'barplot')], 'OS_STATUS: NA')
nc.display([('log2CNA', 'barplot')], ['OS_STATUS; SEQUENCED', 'all_groups'])

nc.display([('log2CNA', 'heatmap')], 'OS_STATUS: NA')
nc.display([('log2CNA', 'heatmap'), ('gistic', 'heatmap')], ['OS_STATUS', 'all_groups'])

nc._exportData("gistic")

nc.display([('log2CNA', 'barplot')], 'TCGA.04.1331.01')

nc.display([(('gistic', 'raw'), "size")], 'TCGA.04.1331.01')
nc.display([(('gistic', 'raw'), "glyph2_shape")], 'TCGA.04.1331.01')
# Error test
#nc.display([(('gistic', 'raw'), 'gg')])
nc.display([(('gistic', 'raw'), 'glyph1_size'), (('gistic', 'raw'), 'size')], 'TCGA.04.1331.01')

nc.display([(('gistic', 'raw'), "map_staining")])
nc.display([(('gistic', 'raw'), "map_staining"), (('gistic', 'raw'), "map_staining")]) # Second version should raise an error

nc.defineModules("data/cellcycle_v1.0.gmt")
nc.averageModule("gistic") # TODO Warning might be to fix
nc._exportData("gistic", "moduleAverage")

